"""
sumo_utils.py
-------------
Automated pipeline for AutoTactix:
1. Converts GPS point + radius to an OSM bounding box
2. Downloads live map data via Overpass API with mirror failover
3. Compiles a geo-referenced SUMO network with netconvert
4. Generates random heavy traffic using SUMO's randomTrips.py
5. Executes sumo-gui via TraCI with high-resolution view controls
"""

import logging
import math
import os
import subprocess
import sys
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple

import requests
import sumolib
import traci

logger = logging.getLogger("autotactix.sumo_utils")

BASE_DIR = Path(__file__).resolve().parent
NETWORKS_DIR = BASE_DIR / "networks"
NETWORKS_DIR.mkdir(parents=True, exist_ok=True)

SUMO_HOME = Path(os.environ.get("SUMO_HOME", "/usr/share/sumo"))


@dataclass
class SimulationJob:
    job_id: str
    net_file: str
    num_vehicles: int
    status: str = "pending"  # pending, preparing, running, finished, error, stopped
    message: str = "Initializing simulation..."
    injected: int = 0
    novnc_url: Optional[str] = None


def force_cleanup_traci():
    """Forcefully closes lingering TraCI connections and terminates zombie SUMO processes."""
    try:
        if hasattr(traci, "_connections"):
            for label in list(traci._connections.keys()):
                try:
                    traci.switch(label)
                    traci.close()
                except Exception:
                    pass
            traci._connections.clear()
    except Exception as exc:
        logger.warning("Error clearing TraCI connection registry: %s", exc)

    try:
        if traci.isLoaded():
            traci.close()
    except Exception:
        pass

    try:
        subprocess.run(["pkill", "-9", "-f", "sumo"], stderr=subprocess.DEVNULL, stdout=subprocess.DEVNULL)
        time.sleep(0.5)
    except (FileNotFoundError, Exception):
        pass


def bbox_from_point(lat: float, lon: float, radius_m: float) -> Tuple[float, float, float, float]:
    """Builds a (south, west, north, east) bounding box around a lat/lon point."""
    deg_lat_per_m = 1.0 / 111320.0
    deg_lon_per_m = 1.0 / (111320.0 * math.cos(math.radians(lat)))
    d_lat = radius_m * deg_lat_per_m
    d_lon = radius_m * deg_lon_per_m
    return (lat - d_lat, lon - d_lon, lat + d_lat, lon + d_lon)


def download_osm_data(bbox: Tuple[float, float, float, float], output_osm_path: Path) -> Path:
    """Downloads OSM road network data from robust Overpass API mirrors with short timeouts."""
    south, west, north, east = bbox
    query = (
        "[out:xml][timeout:25];\n"
        "(\n"
        f'  way["highway"]({south},{west},{north},{east});\n'
        ");\n"
        "(._;>;);\n"
        "out body;\n"
    )
    headers = {
        "User-Agent": "AutoTactix-Simulation-System/1.0",
        "Content-Type": "application/x-www-form-urlencoded",
    }
    mirrors = [
        "https://overpass.kumi.systems/api/interpreter",
        "https://overpass-api.de/api/interpreter",
        "https://overpass.private.coffee/api/interpreter",
        "https://overpass.nchc.org.tw/api/interpreter",
        "https://lz4.overpass-api.de/api/interpreter",
    ]
    last_error = None
    for url in mirrors:
        try:
            logger.info("Downloading OSM data from Overpass mirror: %s", url)
            resp = requests.post(url, data={"data": query}, headers=headers, timeout=18)
            resp.raise_for_status()
            if b"<osm" not in resp.content.lower():
                raise ValueError("Response does not contain valid XML OSM data.")
            output_osm_path.write_bytes(resp.content)
            logger.info("OSM data saved to: %s", output_osm_path)
            return output_osm_path
        except Exception as exc:
            logger.warning("Overpass mirror %s failed: %s", url, exc)
            last_error = exc
    raise RuntimeError(f"All Overpass API mirrors failed or timed out. Last error: {last_error}")


def generate_sumo_net(osm_file: Path, net_file: Path) -> Path:
    """Runs netconvert to create a fully junction-joined SUMO network from OSM data."""
    cmd = [
        "netconvert",
        "--osm-files", str(osm_file),
        "-o", str(net_file),
        "--geometry.remove", "true",
        "--roundabouts.guess", "true",
        "--ramps.guess", "true",
        "--junctions.join", "true",
        "--tls.guess-signals", "true",
        "--tls.discard-simple", "true",
        "--tls.join", "true",
        "--ignore-errors", "true",
    ]
    logger.info("Running netconvert: %s", " ".join(cmd))
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"netconvert failed: {proc.stderr}")
    return net_file


def generate_heavy_random_traffic(net_file: Path, routes_file: Path, period: float, seed: int = 42) -> Path:
    """Uses randomTrips.py to generate heavy multi-edge traffic routes across the network."""
    random_trips_script = SUMO_HOME / "tools" / "randomTrips.py"
    if not random_trips_script.exists():
        random_trips_script = Path("/usr/share/sumo/tools/randomTrips.py")

    trips_file = routes_file.with_suffix(".trips.xml")

    cmd = [
        sys.executable, str(random_trips_script),
        "-n", str(net_file),
        "-o", str(trips_file),
        "-r", str(routes_file),
        "-b", "0",
        "-e", "3600",
        "-p", str(max(0.05, period)),
        "--fringe-factor", "10",
        "--validate",
        "--seed", str(seed),
        "--min-distance", "20",
    ]
    logger.info("Generating heavy random traffic via randomTrips.py...")
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"randomTrips.py failed: {proc.stderr}")
    return routes_file


class SimulationRunner:
    def __init__(self):
        self._lock = threading.Lock()
        self._running = False
        self._stop_requested = False
        self.current_job: Optional[SimulationJob] = None
        self._thread: Optional[threading.Thread] = None

    def is_busy(self) -> bool:
        with self._lock:
            return self._running

    def list_networks(self) -> List[str]:
        """Lists user network files in the networks directory."""
        if not NETWORKS_DIR.exists():
            return []
        return [
            f.name
            for f in NETWORKS_DIR.glob("*.net.xml")
            if not f.name.startswith("repaired_") and not f.name.startswith("auto_")
        ]

    def stop(self):
        logger.info("Stopping simulation runner...")
        self._stop_requested = True
        force_cleanup_traci()

        if self._thread and self._thread.is_alive() and threading.current_thread() != self._thread:
            self._thread.join(timeout=3.0)

        with self._lock:
            self._running = False
            if self.current_job and self.current_job.status in ("pending", "preparing", "running"):
                self.current_job.status = "stopped"
                self.current_job.message = "Simulation manually stopped by user."

    def start_in_background(
        self,
        job: SimulationJob,
        center_lat: float,
        center_lon: float,
        radius: float,
        num_vehicles: int,
        injection_rate: float,
        step_delay: int,
        custom_net_file: Optional[str] = None,
    ):
        self._thread = threading.Thread(
            target=self.start,
            args=(
                job,
                center_lat,
                center_lon,
                radius,
                num_vehicles,
                injection_rate,
                step_delay,
                custom_net_file,
            ),
            daemon=True,
        )
        self._thread.start()

    def start(
        self,
        job: SimulationJob,
        center_lat: float,
        center_lon: float,
        radius: float,
        num_vehicles: int,
        injection_rate: float,
        step_delay: int,
        custom_net_file: Optional[str] = None,
    ):
        with self._lock:
            if self._running:
                job.status = "error"
                job.message = "Runner is already busy with another job."
                return
            self._running = True
            self._stop_requested = False
            self.current_job = job

        job.status = "preparing"
        job.novnc_url = None
        os.environ["DISPLAY"] = ":99"
        force_cleanup_traci()

        osm_file = Path(f"/tmp/auto_map_{job.job_id}.osm.xml")
        active_net_file = Path(f"/tmp/auto_net_{job.job_id}.net.xml")
        routes_file = Path(f"/tmp/auto_routes_{job.job_id}.rou.xml")

        try:
            # 1. Download OSM or Use Custom Network File
            if custom_net_file and (NETWORKS_DIR / custom_net_file).exists():
                job.message = f"Loading network {custom_net_file}..."
                active_net_file = NETWORKS_DIR / custom_net_file
            else:
                job.message = f"Downloading OpenStreetMap data for GPS ({center_lat:.4f}, {center_lon:.4f})..."
                bbox = bbox_from_point(center_lat, center_lon, radius)
                download_osm_data(bbox, osm_file)

                if self._stop_requested:
                    return

                job.message = "Compiling geo-referenced SUMO network with netconvert..."
                generate_sumo_net(osm_file, active_net_file)

            if self._stop_requested:
                return

            # 2. Parse Network
            net = sumolib.net.readNet(str(active_net_file))
            drivable_edges = [e for e in net.getEdges() if e.allows("passenger")]
            if not drivable_edges:
                raise RuntimeError("The generated network contains no drivable road edges.")

            # 3. Generate Heavy Random Traffic Routes
            job.message = "Generating random heavy traffic routes across the network..."
            generate_heavy_random_traffic(
                net_file=active_net_file,
                routes_file=routes_file,
                period=injection_rate,
                seed=int(time.time()) % 1000,
            )

            if self._stop_requested:
                return

            # 4. Compute Viewport Coordinates
            cx, cy = 0.0, 0.0
            try:
                cx, cy = net.convertLonLat2XY(center_lon, center_lat)
            except Exception:
                xmin, ymin, xmax, ymax = net.getBoundary()
                cx, cy = (xmin + xmax) / 2.0, (ymin + ymax) / 2.0

            # 5. Launch SUMO GUI
            job.message = "Launching SUMO GUI and establishing connection..."
            sumo_cmd = [
                "sumo-gui",
                "-n", str(active_net_file),
                "-r", str(routes_file),
                "--window-size", "2560,1440",
                "--window-pos", "0,0",
                "--start", "true",
                "--delay", str(step_delay),
            ]

            logger.info("Launching SUMO GUI via TraCI...")
            traci.start(sumo_cmd)

            # 6. Initialize View Settings
            traci.simulationStep()
            view_id = "View #0"
            try:
                traci.gui.setSchema(view_id, "real world")
                half_r = max(150.0, radius)
                traci.gui.setBoundary(view_id, cx - half_r, cy - half_r, cx + half_r, cy + half_r)
                traci.gui.setZoom(view_id, 4500)
            except traci.TraCIException as gui_err:
                logger.warning("TraCI GUI setup failed: %s", gui_err)

            # Mark simulation active and assign noVNC endpoint after sumo-gui is running
            job.status = "running"
            job.novnc_url = "/vnc.html?resize=scale&autoconnect=true&path=websockify"
            job.message = "Simulation active with automated heavy traffic."

            # 7. Simulation Loop
            step = 1
            max_steps = 10000

            while not self._stop_requested and step < max_steps:
                try:
                    traci.simulationStep()
                    step += 1
                    job.injected = traci.simulation.getMinExpectedNumber()

                    if traci.simulation.getMinExpectedNumber() <= 0 and step > 100:
                        break
                except (traci.TraCIException, OSError, Exception):
                    if self._stop_requested:
                        break
                    raise

            if not self._stop_requested:
                job.status = "finished"
                job.message = "Simulation completed successfully."
                time.sleep(3)
            else:
                job.status = "stopped"
                job.message = "Simulation manually stopped by user."

        except Exception as exc:
            if self._stop_requested:
                job.status = "stopped"
                job.message = "Simulation manually stopped by user."
            else:
                logger.exception("Automated simulation workflow failed")
                job.status = "error"
                job.message = f"Error: {str(exc)}"

        finally:
            force_cleanup_traci()
            for tmp_p in (osm_file, Path(f"/tmp/auto_net_{job.job_id}.net.xml"), routes_file, routes_file.with_suffix(".trips.xml")):
                if tmp_p.exists():
                    tmp_p.unlink(missing_ok=True)
            with self._lock:
                self._running = False


runner = SimulationRunner()