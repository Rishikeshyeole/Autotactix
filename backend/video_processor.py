"""
video_processor.py
-------------------
Module 2 backend: Comprehensive Traffic Anomaly Diagnostic Engine.
Performs multi-zone ROI analysis (Lanes, Intersection Box, Crosswalk Zone, Counting Lines),
tracks vehicles & pedestrians with YOLOv8 + ByteTrack, flags anomalies (weaving, stopping,
gridlocking, swerving, jaywalking, wrong-way, accidents, lane drift, slow vehicle hazards),
and calls the Gemini API to generate civil engineering traffic reports.
"""

from __future__ import annotations

import csv
import json
import logging
import math
import os
import shutil
import subprocess
import threading
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

import cv2
import numpy as np
import pandas as pd
import supervision as sv
from shapely.geometry import Point, Polygon
from tabulate import tabulate

logger = logging.getLogger("autotactix.video")

# Thresholds from comprehensive_traffic_analyzer.py
WEAVE_LANE_CHANGE_THRESH = 3
STOPPED_TIME_THRESH_SEC = 5.0
SWERVE_PIXEL_THRESH = 45.0
SLOW_VEHICLE_RATIO = 0.4
GRIDLOCK_TIME_THRESH_SEC = 6.0
ACCIDENT_STOP_THRESH_SEC = 10.0

PEDESTRIAN_CLASS = 0
VEHICLE_CLASSES = {2: "Car", 3: "Motorcycle", 5: "Bus", 7: "Truck"}
CLASS_NAMES = {0: "Pedestrian", 2: "Car", 3: "Motorcycle", 5: "Bus", 7: "Truck"}

MODEL_WEIGHTS = "yolov8n.pt"
CONFIDENCE_THRESHOLD = 0.35

_model_lock = threading.Lock()
_model = None


def _get_model():
    global _model
    if _model is None:
        with _model_lock:
            if _model is None:
                from ultralytics import YOLO
                logger.info("Loading YOLO model: %s", MODEL_WEIGHTS)
                _model = YOLO(MODEL_WEIGHTS)
    return _model


class VideoProcessingError(Exception):
    """Raised for any user-facing video processing problem."""


@dataclass
class AnalysisJob:
    job_id: str
    status: str = "starting"   # starting | running | finished | error
    message: str = ""
    progress: float = 0.0      # 0..1
    output_video_url: Optional[str] = None
    metrics: dict = field(default_factory=dict)
    solutions: list = field(default_factory=list)
    ai_report: str = ""
    started_at: float = field(default_factory=time.time)
    finished_at: Optional[float] = None


def extract_first_frame(video_path: Path) -> tuple[np.ndarray, int, int]:
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise VideoProcessingError(f"Could not open video file: {video_path.name}")
    try:
        ok, frame = cap.read()
        if not ok or frame is None:
            raise VideoProcessingError("Could not read the first frame of the video.")
        height, width = frame.shape[:2]
        return frame, width, height
    finally:
        cap.release()


def frame_to_data_url(frame_bgr: np.ndarray) -> str:
    import base64
    ok, buf = cv2.imencode(".png", frame_bgr)
    if not ok:
        raise VideoProcessingError("Failed to encode extracted frame as PNG.")
    b64 = base64.b64encode(buf.tobytes()).decode("ascii")
    return f"data:image/png;base64,{b64}"


def scale_coordinates(
    points: list[list[float]], canvas_w: float, canvas_h: float, video_w: int, video_h: int
) -> list[list[float]]:
    if canvas_w <= 0 or canvas_h <= 0:
        raise VideoProcessingError("Invalid canvas dimensions supplied for scaling.")
    sx = video_w / canvas_w
    sy = video_h / canvas_h
    return [[round(x * sx, 2), round(y * sy, 2)] for x, y in points]


def _make_video_writer(out_path: Path, fps: float, size: tuple[int, int]) -> cv2.VideoWriter:
    for fourcc_str in ("mp4v", "avc1", "MJPG"):
        fourcc = cv2.VideoWriter_fourcc(*fourcc_str)
        writer = cv2.VideoWriter(str(out_path), fourcc, fps, size)
        if writer.isOpened():
            return writer
        writer.release()
    raise VideoProcessingError("No usable video codec found for writing the output video.")


def convert_to_web_h264(input_path: Path, output_path: Path) -> None:
    """Converts OpenCV generated raw video into web-playable H.264/YUV420p video."""
    ffmpeg_bin = shutil.which("ffmpeg")
    
    if not ffmpeg_bin:
        logger.error("FFmpeg binary not found in PATH. Browser playback requires H.264 conversion.")
        if input_path.exists():
            shutil.move(str(input_path), str(output_path))
        return

    cmd = [
        ffmpeg_bin, "-y",
        "-i", str(input_path),
        "-an",  # Strip non-existent audio stream to prevent sync headers error
        "-vf", "scale=trunc(iw/2)*2:trunc(ih/2)*2",  # Force even dimensions required for H.264 yuv420p
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        "-preset", "fast",
        "-crf", "23",
        "-movflags", "+faststart",  # Place MOOV atom at beginning for immediate HTML5 web streaming
        str(output_path)
    ]
    logger.info("Executing FFmpeg conversion to web-compatible H.264 format...")
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if res.returncode != 0 or not output_path.exists() or output_path.stat().st_size == 0:
            logger.error("FFmpeg conversion failed (code %d):\nSTDERR: %s", res.returncode, res.stderr)
            if input_path.exists():
                shutil.move(str(input_path), str(output_path))
        else:
            logger.info("FFmpeg web H.264 conversion successful: %s (%d bytes)", 
                        output_path.name, output_path.stat().st_size)
    except Exception as exc:
        logger.exception("FFmpeg process crashed: %s", exc)
        if input_path.exists():
            shutil.move(str(input_path), str(output_path))


def generate_traffic_solutions(detected_issues_summary: dict) -> list[dict]:
    lane_weaving_count = detected_issues_summary.get("Aggressive Lane Weaving", 0)
    illegal_stop_count = detected_issues_summary.get("Illegal Stopping / Parking", 0)
    gridlock_count = detected_issues_summary.get("Gridlocking (Intersection Block)", 0)
    swerve_count = detected_issues_summary.get("Sudden Swerve (Pothole/Debris Evasion)", 0)
    wrong_way_count = detected_issues_summary.get("Wrong-Way Driving", 0)
    jaywalk_count = detected_issues_summary.get("Pedestrian Crosswalk Encroachment (Jaywalking)", 0)

    return [
        {
            "Tier": "1. Temporary (Immediate)",
            "Solution_Name": "Plastic Dividers & Flexible Delineator Posts",
            "Target_Issues": "Lane Weaving, Illegal Stopping, Wrong-Way Entry",
            "Trigger_Reason": f"Detected {lane_weaving_count} weaving and {wrong_way_count} wrong-way instances.",
            "Est_Cost": "Low ($5,000 - $15,000)",
            "Deployment_Time": "1 - 3 Days",
            "Lifespan": "6 - 12 Months",
            "Traffic_Flow_Impact": "Moderate (+15% throughput)"
        },
        {
            "Tier": "2. Short-Term (Operational)",
            "Solution_Name": "Smart Adaptive Signal Control & ANPR Enforcement",
            "Target_Issues": "Gridlocking, Pedestrian Encroachment, Signal Delays",
            "Trigger_Reason": f"Detected {gridlock_count} intersection blocks and {jaywalk_count} jaywalking events.",
            "Est_Cost": "Medium ($40,000 - $100,000)",
            "Deployment_Time": "1 - 2 Months",
            "Lifespan": "3 - 5 Years",
            "Traffic_Flow_Impact": "High (+30% signal efficiency)"
        },
        {
            "Tier": "3. Medium-Term (Tactical)",
            "Solution_Name": "Road Resurfacing & Alternative Bypass Rerouting",
            "Target_Issues": "Sudden Swerving (Potholes), Slow Vehicles, Channelized Flow",
            "Trigger_Reason": f"Detected {swerve_count} swerving maneuvers due to road surface hazards.",
            "Est_Cost": "High ($200,000 - $750,000)",
            "Deployment_Time": "3 - 6 Months",
            "Lifespan": "5 - 10 Years",
            "Traffic_Flow_Impact": "High (+45% travel speed recovery)"
        },
        {
            "Tier": "4. Permanent (Infrastructure)",
            "Solution_Name": "Elevated Flyover Interchange & Grade-Separated Skywalk",
            "Target_Issues": "Severe Gridlocking, Structural Bottlenecks, Pedestrian Conflicts",
            "Trigger_Reason": "High persistent vehicle density and multi-direction flow conflicts.",
            "Est_Cost": "Very High ($5M - $20M)",
            "Deployment_Time": "18 - 36 Months",
            "Lifespan": "50+ Years",
            "Traffic_Flow_Impact": "Maximum (+80% bottleneck elimination)"
        }
    ]


def generate_ai_traffic_report(
    detected_issues_summary: dict, total_vehicles: int, video_duration_sec: float
) -> str:
    # 1. HARDCODE YOUR API KEY HERE OR PASS IT VIA ENVIRONMENT VARIABLE
    api_key = os.getenv("GCP_API_KEY").strip()
    
    # If API key is empty, set your key string directly below:
    if not api_key:
        api_key = "AQ.Ab8RN6ISTVeserkHD4Mk-DDCMGXS9XsqTOgsk3wwpzkQlnW0Vg"

    current_date_str = datetime.now().strftime("%B %d, %Y")
    duration_hours = round(video_duration_sec / 3600.0, 4) if video_duration_sec > 0 else 0.001

    payload = {
        "report_date": current_date_str,
        "surveillance_metadata": {
            "total_vehicles_monitored": total_vehicles,
            "observation_duration_seconds": round(video_duration_sec, 2),
            "estimated_hourly_volume": round(total_vehicles / duration_hours, 1)
        },
        "detected_anomalies_breakdown": detected_issues_summary
    }

    if not api_key or api_key == "YOUR_GEMINI_API_KEY_HERE":
        logger.error("GEMINI_API_KEY is missing.")
        return (
            f"# AutoTactix Engineering Diagnostic Summary ({current_date_str})\n\n"
            f"**Monitored Vehicles:** {total_vehicles} | **Duration:** {video_duration_sec:.1f}s\n\n"
            f"### Detected Anomaly Breakdown\n" +
            "\n".join([f"- **{k}:** {v} instances" for k, v in detected_issues_summary.items()]) +
            "\n\n---\n⚠️ **Error: Invalid or Missing `GEMINI_API_KEY`.**\n"
            "Please paste your key into `video_processor.py` on line 135 or set the `GEMINI_API_KEY` environment variable."
        )

    try:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=api_key)
        system_instruction = (
            "You are an expert Senior Traffic Engineer, Road Safety Auditor, and Urban Infrastructure Planning Consultant. "
            "Your objective is to produce a rigorous, highly technical, and professional Traffic Safety & Anomaly Diagnostics Report in Markdown.\n"
            "Adhere strictly to civil engineering terminology, calculate exact incident rates, provide risk prioritization matrices, "
            "and detail actionable temporary, short-term, medium-term, and permanent mitigation packages."
        )

        user_prompt = f"""
        Analyze the following real-time computer vision traffic detection dataset:

        ```json
        {json.dumps(payload, indent=2)}
        ```

        Generate a comprehensive engineering report in Markdown following this structure:
        1. HEADER & EXECUTIVE SUMMARY (Incident Rate per 1,000 Vehicles, Hourly Volume).
        2. RISK PRIORITIZATION & SEVERITY INDEX MATRIX (Life-Safety, Pavement, Flow Disruption).
        3. IMMEDIATE TEMPORARY SOLUTIONS (1–7 Days).
        4. SHORT-TO-MEDIUM TERM REMEDIES (1–6 Months).
        5. PERMANENT INFRASTRUCTURE SOLUTIONS (1–3 Years).
        6. COMPARATIVE FEASIBILITY & BENEFIT-COST MATRIX (Markdown Table with Tier, Intervention, Cost, Impact, BCR).
        7. STANDARDS COMPLIANCE & REGULATORY REFERENCES (MUTCD, IRC, AASHTO).
        8. ACTIONABLE FIELD WORK-ORDER ROADMAP.
        """

        config = types.GenerateContentConfig(
            system_instruction=system_instruction,
            temperature=0.15,
            top_p=0.9,
            max_output_tokens=4096
        )

        # Verified active Gemini models
        candidate_models = ["gemini-3.6-flash","gemini-3.5-flash", "gemini-3.5-flash-lite"] 
        last_err = None

        for model_name in candidate_models:
            try:
                logger.info("Attempting Gemini report generation with model: %s", model_name)
                resp = client.models.generate_content(model=model_name, contents=user_prompt, config=config)
                if resp and resp.text:
                    logger.info("Successfully generated Gemini report with %s", model_name)
                    return resp.text
            except Exception as e:
                logger.warning("Gemini model %s failed: %s", model_name, e)
                last_err = e

        return (
            f"# AutoTactix Engineering Diagnostic Summary ({current_date_str})\n\n"
            f"**Monitored Vehicles:** {total_vehicles} | **Duration:** {video_duration_sec:.1f}s\n\n"
            f"### Detected Anomaly Breakdown\n" +
            "\n".join([f"- **{k}:** {v} instances" for k, v in detected_issues_summary.items()]) +
            f"\n\n---\n⚠️ **Gemini API Model Error:** All candidate models failed. Last error: `{last_err}`"
        )

    except Exception as exc:
        logger.exception("Gemini API initialization or call failed")
        return (
            f"# AutoTactix Engineering Diagnostic Summary ({current_date_str})\n\n"
            f"**Monitored Vehicles:** {total_vehicles} | **Duration:** {video_duration_sec:.1f}s\n\n"
            f"### Detected Anomaly Breakdown\n" +
            "\n".join([f"- **{k}:** {v} instances" for k, v in detected_issues_summary.items()]) +
            f"\n\n---\n⚠️ **Gemini API Error:** `{str(exc)}`"
        )


def process_video(
    job: AnalysisJob,
    video_path: Path,
    output_path: Path,
    canvas_width: float,
    canvas_height: float,
    lane_zones_raw: list[list[list[float]]],
    intersection_zone_raw: Optional[list[list[float]]],
    crosswalk_zone_raw: Optional[list[list[float]]],
    counting_lines_raw: list[list[list[float]]],
) -> None:
    raw_output_path = output_path.with_name(f"raw_{output_path.name}")
    try:
        job.status = "running"
        model = _get_model()

        cap = cv2.VideoCapture(str(video_path))
        if not cap.isOpened():
            raise VideoProcessingError(f"Could not open video file: {video_path.name}")

        fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
        video_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        video_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) or 0

        # Build Shapely Polygons
        lane_polygons = {}
        for i, poly in enumerate(lane_zones_raw):
            if len(poly) >= 3:
                scaled = scale_coordinates(poly, canvas_width, canvas_height, video_w, video_h)
                lane_polygons[f"Lane_{i + 1}"] = Polygon(scaled)

        intersection_polygon = None
        if intersection_zone_raw and len(intersection_zone_raw) >= 3:
            scaled = scale_coordinates(intersection_zone_raw, canvas_width, canvas_height, video_w, video_h)
            intersection_polygon = Polygon(scaled)

        crosswalk_polygon = None
        if crosswalk_zone_raw and len(crosswalk_zone_raw) >= 3:
            scaled = scale_coordinates(crosswalk_zone_raw, canvas_width, canvas_height, video_w, video_h)
            crosswalk_polygon = Polygon(scaled)

        line_zones = []
        for i, line in enumerate(counting_lines_raw):
            if len(line) >= 2:
                scaled = scale_coordinates(line, canvas_width, canvas_height, video_w, video_h)
                (x1, y1), (x2, y2) = scaled[0], scaled[1]
                lz = sv.LineZone(start=sv.Point(x1, y1), end=sv.Point(x2, y2))
                line_zones.append((f"Line {i + 1}", lz))

        writer = _make_video_writer(raw_output_path, fps, (video_w, video_h))
        tracker = sv.ByteTrack(frame_rate=int(round(fps)) or 25)

        vehicle_history = defaultdict(lambda: {
            'positions': deque(maxlen=int(fps * 3)),
            'lanes_visited': [],
            'lane_change_count': 0,
            'stationary_start': None,
            'intersection_stop_start': None,
            'decel_flag': False,
            'issues_logged': set(),
            'type': 'Vehicle'
        })

        detected_issues_summary = defaultdict(int)
        class_totals = {name: 0 for name in CLASS_NAMES.values()}
        seen_track_ids = set()

        frame_idx = 0

        while True:
            ok, frame = cap.read()
            if not ok:
                break

            frame_idx += 1
            timestamp_sec = round(frame_idx / fps, 2)

            results = model(frame, verbose=False, conf=CONFIDENCE_THRESHOLD)[0]
            detections = sv.Detections.from_ultralytics(results)
            detections = detections[np.isin(detections.class_id, list(CLASS_NAMES.keys()))]
            detections = tracker.update_with_detections(detections)

            # Draw ROI Polygons
            for lane_name, polygon in lane_polygons.items():
                pts = np.array(polygon.exterior.coords, np.int32).reshape((-1, 1, 2))
                cv2.polylines(frame, [pts], isClosed=True, color=(255, 191, 0), thickness=2)
                cv2.putText(frame, lane_name, (pts[0][0][0], pts[0][0][1] - 8),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 191, 0), 2)

            if intersection_polygon:
                pts = np.array(intersection_polygon.exterior.coords, np.int32).reshape((-1, 1, 2))
                cv2.polylines(frame, [pts], isClosed=True, color=(0, 0, 255), thickness=2)
                cv2.putText(frame, "INTERSECTION", (pts[0][0][0], pts[0][0][1] - 8),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)

            if crosswalk_polygon:
                pts = np.array(crosswalk_polygon.exterior.coords, np.int32).reshape((-1, 1, 2))
                cv2.polylines(frame, [pts], isClosed=True, color=(255, 0, 255), thickness=2)
                cv2.putText(frame, "CROSSWALK", (pts[0][0][0], pts[0][0][1] - 8),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 0, 255), 2)

            current_frame_speeds = defaultdict(list)

            if detections.tracker_id is not None:
                for box, track_id, cls_id in zip(detections.xyxy, detections.tracker_id, detections.class_id):
                    if track_id is None:
                        continue
                    x1, y1, x2, y2 = map(int, box)
                    cx, cy = (x1 + x2) // 2, y2
                    obj_point = Point(cx, cy)
                    cls_name = CLASS_NAMES.get(int(cls_id), "Object")

                    if int(track_id) not in seen_track_ids:
                        seen_track_ids.add(int(track_id))
                        class_totals[cls_name] = class_totals.get(cls_name, 0) + 1

                    if int(cls_id) == PEDESTRIAN_CLASS:
                        cv2.circle(frame, (cx, cy), 4, (255, 0, 255), -1)
                        cv2.putText(frame, f"Ped:{track_id}", (x1, y1 - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 0, 255), 1)
                        if crosswalk_polygon and not crosswalk_polygon.contains(obj_point):
                            for lane_name, lane_poly in lane_polygons.items():
                                if lane_poly.contains(obj_point):
                                    issue = "Pedestrian Crosswalk Encroachment (Jaywalking)"
                                    detected_issues_summary[issue] += 1
                                    cv2.putText(frame, "⚠️ JAYWALKER", (x1, y1 - 15), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 2)
                        continue

                    v_data = vehicle_history[int(track_id)]
                    v_data['type'] = cls_name
                    v_data['positions'].append((cx, cy, timestamp_sec))

                    current_lane = "Unknown"
                    for lane_name, polygon in lane_polygons.items():
                        if polygon.contains(obj_point):
                            current_lane = lane_name
                            break

                    if len(v_data['lanes_visited']) == 0:
                        if current_lane != "Unknown":
                            v_data['lanes_visited'].append(current_lane)
                    elif v_data['lanes_visited'][-1] != current_lane and current_lane != "Unknown":
                        v_data['lanes_visited'].append(current_lane)
                        v_data['lane_change_count'] += 1

                    active_issues = []
                    speed_px_sec = 0.0

                    if len(v_data['positions']) > int(fps):
                        old_x, old_y, old_t = v_data['positions'][0]
                        dt = timestamp_sec - old_t
                        dx = cx - old_x
                        dy = cy - old_y
                        distance_px = math.hypot(dx, dy)
                        speed_px_sec = distance_px / dt if dt > 0 else 0.0

                        if current_lane != "Unknown":
                            current_frame_speeds[current_lane].append(speed_px_sec)

                        if v_data['lane_change_count'] >= WEAVE_LANE_CHANGE_THRESH:
                            active_issues.append("Aggressive Lane Weaving")

                        if speed_px_sec < 4.0 and current_lane != "Unknown":
                            if v_data['stationary_start'] is None:
                                v_data['stationary_start'] = timestamp_sec
                            elif (timestamp_sec - v_data['stationary_start']) >= STOPPED_TIME_THRESH_SEC:
                                active_issues.append("Illegal Stopping / Parking")
                        else:
                            v_data['stationary_start'] = None

                        if intersection_polygon and intersection_polygon.contains(obj_point):
                            if speed_px_sec < 4.0:
                                if v_data['intersection_stop_start'] is None:
                                    v_data['intersection_stop_start'] = timestamp_sec
                                elif (timestamp_sec - v_data['intersection_stop_start']) >= GRIDLOCK_TIME_THRESH_SEC:
                                    active_issues.append("Gridlocking (Intersection Block)")
                            else:
                                v_data['intersection_stop_start'] = None
                        else:
                            v_data['intersection_stop_start'] = None

                        lateral_speed = abs(dx) / dt if dt > 0 else 0.0
                        if lateral_speed > SWERVE_PIXEL_THRESH and current_lane != "Unknown":
                            active_issues.append("Sudden Swerve (Pothole/Debris Evasion)")

                        if dy < -30.0:
                            active_issues.append("Wrong-Way Driving")

                        if dt > 1.5:
                            prev_speed = math.hypot(cx - v_data['positions'][-2][0], cy - v_data['positions'][-2][1])
                            if prev_speed > 25.0 and speed_px_sec < 2.0:
                                v_data['decel_flag'] = True
                        
                        if v_data['decel_flag'] and v_data['stationary_start'] is not None:
                            if (timestamp_sec - v_data['stationary_start']) >= ACCIDENT_STOP_THRESH_SEC:
                                active_issues.append("Traffic Accident / Breakdown")

                        if current_lane == "Unknown" and speed_px_sec > 10.0:
                            active_issues.append("Lane Line Drift (Ambiguous Markings)")

                    if current_lane in current_frame_speeds and len(current_frame_speeds[current_lane]) > 2:
                        avg_lane_speed = np.mean(current_frame_speeds[current_lane])
                        if speed_px_sec < (avg_lane_speed * SLOW_VEHICLE_RATIO) and speed_px_sec > 3.0:
                            active_issues.append("Slow-Moving Vehicle Hazard")

                    for issue in active_issues:
                        if issue not in v_data['issues_logged']:
                            v_data['issues_logged'].add(issue)
                            detected_issues_summary[issue] += 1

                    box_color = (0, 0, 255) if active_issues else (0, 255, 0)
                    cv2.rectangle(frame, (x1, y1), (x2, y2), box_color, 2)
                    cv2.circle(frame, (cx, cy), 4, (0, 0, 255), -1)

                    hud_label = f"ID:{track_id} {cls_name} | LC:{v_data['lane_change_count']}"
                    if active_issues:
                        hud_label += f" | ⚠️ {active_issues[0]}"
                    cv2.putText(frame, hud_label, (x1, y1 - 8), cv2.FONT_HERSHEY_SIMPLEX, 0.45, box_color, 2)

            # HUD Overlay
            cv2.rectangle(frame, (10, 10), (450, 140), (0, 0, 0), -1)
            cv2.putText(frame, f"Active Vehicles Monitored: {len(detections)}", (20, 35),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
            cv2.putText(frame, f"Total Detected Anomalies: {sum(detected_issues_summary.values())}", (20, 65),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)

            y_pos = 95
            for issue_title, count in list(detected_issues_summary.items())[:2]:
                cv2.putText(frame, f"{issue_title[:28]}..: {count}", (20, y_pos),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
                y_pos += 25

            writer.write(frame)

            if total_frames > 0:
                job.progress = min(0.95, frame_idx / total_frames)

        cap.release()
        writer.release()

        # Re-encode raw output to web-compatible H.264
        convert_to_web_h264(raw_output_path, output_path)

        total_duration_sec = frame_idx / fps if fps > 0 else 0.0
        solutions = generate_traffic_solutions(detected_issues_summary)
        ai_report = generate_ai_traffic_report(detected_issues_summary, len(seen_track_ids), total_duration_sec)

        job.metrics = {
            "detected_anomalies_summary": dict(detected_issues_summary),
            "vehicle_class_totals": class_totals,
            "total_unique_vehicles": len(seen_track_ids),
            "total_duration_sec": round(total_duration_sec, 2),
            "frames_processed": frame_idx,
            "fps": round(fps, 2),
        }
        job.solutions = solutions
        job.ai_report = ai_report
        job.output_video_url = f"/static/outputs/{output_path.name}"
        job.progress = 1.0
        job.status = "finished"
        job.message = "Analysis complete."

    except VideoProcessingError as exc:
        job.status = "error"
        job.message = str(exc)
        logger.warning("Video job %s failed: %s", job.job_id, exc)
    except Exception as exc:
        job.status = "error"
        job.message = f"Unexpected error during video analysis: {exc}"
        logger.exception("Video job %s crashed", job.job_id)
    finally:
        if raw_output_path.exists():
            raw_output_path.unlink(missing_ok=True)
        job.finished_at = time.time()


def parse_lane_json(raw: str) -> tuple[list, Optional[list], Optional[list], list]:
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise VideoProcessingError(f"Invalid lane annotation JSON: {exc}") from exc
    lane_zones = data.get("lane_zones", [])
    intersection_zone = data.get("intersection_zone", None)
    crosswalk_zone = data.get("crosswalk_zone", None)
    counting_lines = data.get("counting_lines", [])
    return lane_zones, intersection_zone, crosswalk_zone, counting_lines