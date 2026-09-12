"""
app.py
------
AutoTactix — Smart Traffic Management & Simulation System.
"""

from __future__ import annotations

import logging
import shutil
import threading
import time
import uuid
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

import sumo_utils
import video_processor as vproc

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("autotactix.app")

BASE_DIR = Path(__file__).resolve().parent
UPLOADS_DIR = BASE_DIR / "uploads"
OUTPUTS_DIR = BASE_DIR / "outputs"
STATIC_DIR = BASE_DIR / "static"
NETWORKS_DIR = sumo_utils.NETWORKS_DIR

for d in (UPLOADS_DIR, OUTPUTS_DIR, STATIC_DIR, NETWORKS_DIR):
    d.mkdir(parents=True, exist_ok=True)

MAX_VIDEO_BYTES = 500 * 1024 * 1024
ALLOWED_VIDEO_SUFFIXES = {".mp4", ".avi", ".mov"}
ALLOWED_NETWORK_SUFFIX = ".net.xml"

app = FastAPI(title="AutoTactix", description="Smart Traffic Management & Simulation System")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static/outputs", StaticFiles(directory=str(OUTPUTS_DIR)), name="static-outputs")
app.mount("/static/uploads", StaticFiles(directory=str(UPLOADS_DIR)), name="static-uploads")

_sim_jobs: dict[str, sumo_utils.SimulationJob] = {}
_video_jobs: dict[str, vproc.AnalysisJob] = {}
_video_sources: dict[str, Path] = {}


# ---------------------------------------------------------------------------
# Module 1: SUMO simulation
# ---------------------------------------------------------------------------
class SimulateRequest(BaseModel):
    center_lat: float
    center_lon: float
    radius: float = Field(default=300.0, gt=0, le=10000)
    network_file: Optional[str] = None
    num_vehicles: int = Field(default=500, ge=1, le=5000)
    injection_rate: float = Field(default=0.25, gt=0, le=60)
    step_delay: int = Field(default=80, ge=0, le=5000)


@app.get("/api/networks")
@app.get("/networks")
def list_networks():
    return {"networks": sumo_utils.runner.list_networks()}


@app.post("/api/networks/upload")
@app.post("/networks/upload")
async def upload_network(file: UploadFile = File(...)):
    if not file.filename.endswith(ALLOWED_NETWORK_SUFFIX):
        raise HTTPException(400, f"Network file must end with {ALLOWED_NETWORK_SUFFIX}")
    dest = NETWORKS_DIR / Path(file.filename).name
    with dest.open("wb") as f:
        shutil.copyfileobj(file.file, f)
    return {"saved_as": dest.name}


@app.post("/api/simulate")
@app.post("/simulate")
def start_simulation(req: SimulateRequest):
    job_id = uuid.uuid4().hex[:12]
    job = sumo_utils.SimulationJob(
        job_id=job_id,
        net_file=req.network_file or "auto_osm_network",
        num_vehicles=req.num_vehicles,
    )
    _sim_jobs[job_id] = job

    sumo_utils.runner.start_new_job(
        job,
        req.center_lat,
        req.center_lon,
        req.radius,
        req.num_vehicles,
        req.injection_rate,
        req.step_delay,
        req.network_file,
    )
    return {"job_id": job_id, "status": job.status, "novnc_url": job.novnc_url}


@app.get("/api/simulate/{job_id}")
@app.get("/simulate/{job_id}")
def simulation_status(job_id: str):
    job = _sim_jobs.get(job_id)
    if job is None:
        raise HTTPException(404, "Unknown simulation job id")
    return {
        "job_id": job.job_id,
        "status": job.status,
        "message": job.message,
        "injected": job.injected,
        "num_vehicles": job.num_vehicles,
        "novnc_url": job.novnc_url,
    }


@app.post("/api/simulate/{job_id}/stop")
@app.post("/simulate/{job_id}/stop")
def stop_simulation(job_id: str):
    job = _sim_jobs.get(job_id)
    sumo_utils.runner.stop()
    if job is not None:
        job.status = "stopped"
        job.message = "Simulation manually stopped by user."
    return {"job_id": job_id, "status": "stopped"}


# ---------------------------------------------------------------------------
# Module 2: AI video traffic analysis
# ---------------------------------------------------------------------------
@app.post("/api/extract-first-frame")
@app.post("/extract-first-frame")
async def extract_first_frame(file: UploadFile = File(...)):
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in ALLOWED_VIDEO_SUFFIXES:
        raise HTTPException(400, f"Unsupported video type '{suffix}'. Allowed: {sorted(ALLOWED_VIDEO_SUFFIXES)}")

    video_id = uuid.uuid4().hex[:12]
    dest = UPLOADS_DIR / f"{video_id}{suffix}"

    size = 0
    with dest.open("wb") as out:
        while chunk := await file.read(1024 * 1024):
            size += len(chunk)
            if size > MAX_VIDEO_BYTES:
                out.close()
                dest.unlink(missing_ok=True)
                raise HTTPException(413, "Video exceeds the 500 MB upload limit.")
            out.write(chunk)

    try:
        frame, width, height = vproc.extract_first_frame(dest)
    except vproc.VideoProcessingError as exc:
        dest.unlink(missing_ok=True)
        raise HTTPException(400, str(exc)) from exc

    data_url = vproc.frame_to_data_url(frame)
    _video_sources[video_id] = dest

    return {
        "video_id": video_id,
        "frame_data_url": data_url,
        "video_width": width,
        "video_height": height,
    }


class AnalyzeVideoRequest(BaseModel):
    video_id: str
    canvas_width: float
    canvas_height: float
    lane_annotations: str


@app.post("/api/analyze-video")
@app.post("/analyze-video")
def analyze_video(req: AnalyzeVideoRequest):
    video_path = _video_sources.get(req.video_id)
    if video_path is None or not video_path.exists():
        raise HTTPException(404, "Unknown video_id. Call /api/extract-first-frame first.")

    try:
        lane_zones, intersection_zone, crosswalk_zone, counting_lines = vproc.parse_lane_json(req.lane_annotations)
    except vproc.VideoProcessingError as exc:
        raise HTTPException(400, str(exc)) from exc

    if not lane_zones and not intersection_zone and not crosswalk_zone and not counting_lines:
        raise HTTPException(400, "Draw at least one zone or counting line before processing.")

    job_id = uuid.uuid4().hex[:12]
    job = vproc.AnalysisJob(job_id=job_id)
    _video_jobs[job_id] = job

    output_path = OUTPUTS_DIR / f"output_analyzed_{job_id}.mp4"

    thread = threading.Thread(
        target=vproc.process_video,
        args=(
            job,
            video_path,
            output_path,
            req.canvas_width,
            req.canvas_height,
            lane_zones,
            intersection_zone,
            crosswalk_zone,
            counting_lines,
        ),
        daemon=True,
    )
    thread.start()

    return {"job_id": job_id, "status": job.status}


@app.get("/api/analyze-video/{job_id}")
@app.get("/analyze-video/{job_id}")
def analyze_video_status(job_id: str):
    job = _video_jobs.get(job_id)
    if job is None:
        raise HTTPException(404, "Unknown analysis job id")
    return {
        "job_id": job.job_id,
        "status": job.status,
        "message": job.message,
        "progress": job.progress,
        "output_video_url": job.output_video_url,
        "metrics": job.metrics,
        "solutions": job.solutions,
        "ai_report": job.ai_report,
    }


@app.get("/")
def index():
    index_path = STATIC_DIR / "index.html"
    if not index_path.exists():
        return JSONResponse(
            status_code=200,
            content={"status": "AutoTactix API Online", "docs_url": "/docs"},
        )
    return FileResponse(index_path)


@app.get("/api/health")
def health():
    return {"status": "ok"}