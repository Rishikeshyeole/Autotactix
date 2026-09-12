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
import socket
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


def get_free_port() -> int:
    """Finds an available TCP port on localhost for TraCI communication."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def force_cleanup_traci():
    """Forcefully terminates all SUMO GUI instances and clears lingering TraCI sockets/labels."""
    try:
        main_mod = getattr(traci, "main", None)
        if main_mod and hasattr(main_mod, "_connections"):
            for label in list(main_mod._connections.keys()):
                try:
                    traci.switch(label)
                    traci.close()
                except Exception:
                    pass
            main_mod._connections.clear()
    except Exception as exc:
        logger.warning("Error clearing TraCI main connection registry: %s", exc)

    try:
        if hasattr(traci, "_connections"):
            for label in list(traci._connections.keys()):
                try:
                    traci.switch(label)
                    traci.close()
                except Exception:
                    pass
            traci._connections.clear()
    except Exception:
        pass

    try:
        if traci.isLoaded():
            traci.close()
    except Exception:
        pass

    try:
        subprocess.run(["pkill", "-9", "-f", "sumo"], stderr=subprocess.DEVNULL, stdout=subprocess.DEVNULL)
        subprocess.run(["pkill", "-9", "-f", "sumo-gui"], stderr=subprocess.DEVNULL, stdout=subprocess.DEVNULL)
        time.sleep(0.3)
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
    """Downloads OSM road network data with fast timeouts across multiple Overpass mirrors."""
    south, west, north, east = bbox
    query = (
        "[out:xml][timeout:15];\n"
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
        "https://overpass-api.de/api/interpreter",
        "https://overpass.kumi.systems/api/interpreter",
        "https://overpass.private.coffee/api/interpreter",
        "https://overpass.nchc.org.tw/api/interpreter",
        "https://lz4.overpass-api.de/api/interpreter",
    ]
    last_error = None
    for url in mirrors:
        try:
            logger.info("Downloading OSM data from Overpass mirror: %s", url)
            resp = requests.post(url, data={"data": query}, headers=headers, timeout=(3.0, 6.0))
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
        self.active_job_id: Optional[str] = None
        self.current_job: Optional[SimulationJob] = None

    def is_busy(self) -> bool:
        with self._lock:
            return self.active_job_id is not None

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
        """Stops active simulation and cleans up processes."""
        logger.info("Stopping simulation runner...")
        with self._lock:
            if self.current_job:
                self.current_job.status = "stopped"
                self.current_job.message = "Simulation stopped by user."
            self.active_job_id = None
        force_cleanup_traci()

    def start_new_job(
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
        """Cancels any prior running job and starts a new simulation thread isolated by job_id."""
        with self._lock:
            self.active_job_id = job.job_id
            self.current_job = job

        # Clean up old TraCI / SUMO instances before starting new thread
        force_cleanup_traci()

        thread = threading.Thread(
            target=self._run_job_thread,
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
        thread.start()

    def _is_job_active(self, job_id: str) -> bool:
        with self._lock:
            return self.active_job_id == job_id

    def _run_job_thread(
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
        job_id = job.job_id
        job.status = "preparing"
        job.novnc_url = None
        os.environ["DISPLAY"] = ":99"

        osm_file = Path(f"/tmp/auto_map_{job_id}.osm.xml")
        active_net_file = Path(f"/tmp/auto_net_{job_id}.net.xml")
        routes_file = Path(f"/tmp/auto_routes_{job_id}.rou.xml")

        try:
            if not self._is_job_active(job_id):
                return

            # 1. Download OSM or Use Custom Network File
            if custom_net_file and (NETWORKS_DIR / custom_net_file).exists():
                job.message = f"Loading network {custom_net_file}..."
                active_net_file = NETWORKS_DIR / custom_net_file
            else:
                job.message = f"Downloading OpenStreetMap data for GPS ({center_lat:.4f}, {center_lon:.4f})..."
                bbox = bbox_from_point(center_lat, center_lon, radius)
                download_osm_data(bbox, osm_file)

                if not self._is_job_active(job_id):
                    return

                job.message = "Compiling geo-referenced SUMO network with netconvert..."
                generate_sumo_net(osm_file, active_net_file)

            if not self._is_job_active(job_id):
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

            if not self._is_job_active(job_id):
                return

            # 4. Compute Viewport Coordinates
            cx, cy = 0.0, 0.0
            try:
                cx, cy = net.convertLonLat2XY(center_lon, center_lat)
            except Exception:
                xmin, ymin, xmax, ymax = net.getBoundary()
                cx, cy = (xmin + xmax) / 2.0, (ymin + ymax) / 2.0

            # 5. Get Free Port & Launch SUMO GUI
            traci_port = get_free_port()
            conn_label = f"job_{job_id}"
            job.message = f"Launching SUMO GUI via TraCI on port {traci_port}..."

            sumo_cmd = [
                "sumo-gui",
                "-n", str(active_net_file),
                "-r", str(routes_file),
                "--window-size", "2560,1440",
                "--window-pos", "0,0",
                "--start", "true",
                "--delay", str(step_delay),
            ]

            if not self._is_job_active(job_id):
                return

            logger.info("Launching SUMO GUI on port %d with label '%s'...", traci_port, conn_label)
            traci.start(sumo_cmd, port=traci_port, label=conn_label)

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

            # Mark simulation active
            job.status = "running"
            job.novnc_url = "/vnc.html?resize=scale&autoconnect=true&path=websockify"
            job.message = "Simulation active with automated heavy traffic."

            # 7. Simulation Loop
            step = 1
            max_steps = 10000

            while self._is_job_active(job_id) and step < max_steps:
                try:
                    traci.simulationStep()
                    step += 1
                    job.injected = traci.simulation.getMinExpectedNumber()

                    if traci.simulation.getMinExpectedNumber() <= 0 and step > 100:
                        break
                except (traci.TraCIException, OSError, Exception):
                    if not self._is_job_active(job_id):
                        break
                    raise

            if self._is_job_active(job_id):
                job.status = "finished"
                job.message = "Simulation completed successfully."

        except Exception as exc:
            if self._is_job_active(job_id):
                logger.exception("Automated simulation workflow failed")
                job.status = "error"
                job.message = f"Error: {str(exc)}"

        finally:
            # CRITICAL: Only clean up if this job is STILL the active job!
            # If a newer job started, DO NOT kill its process or delete its state!
            with self._lock:
                is_still_current = (self.active_job_id == job_id)
                if is_still_current:
                    self.active_job_id = None

            if is_still_current:
                force_cleanup_traci()

            for tmp_p in (osm_file, Path(f"/tmp/auto_net_{job_id}.net.xml"), routes_file, routes_file.with_suffix(".trips.xml")):
                if tmp_p.exists():
                    tmp_p.unlink(missing_ok=True)


runner = SimulationRunner()