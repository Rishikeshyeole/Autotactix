# syntax=docker/dockerfile:1
FROM python:3.11-slim-bookworm

LABEL maintainer="AutoTactix"
LABEL description="Smart Traffic Management & Simulation System — SUMO/TraCI + YOLOv8/Supervision"

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    DISPLAY=:99 \
    SUMO_HOME=/usr/share/sumo \
    NOVNC_PORT=6080 \
    VNC_PORT=5900 \
    APP_PORT=8000

# ---------------------------------------------------------------------------
# System dependencies:
#   sumo / sumo-tools / sumo-doc  -> SUMO + sumo-gui + $SUMO_HOME/tools (traci/sumolib source)
#   xvfb, x11vnc, fluxbox         -> virtual display + VNC server + window manager (prevents blank screen)
#   novnc, websockify             -> browser-accessible noVNC bridge on 6080
#   libgl1, libglib2.0-0, libsm6, libxext6, libxrender1 -> required by OpenCV / Qt (sumo-gui) at runtime
#   libspatialindex-dev           -> backs the optional `rtree` package for fast edge lookups in sumolib
# ---------------------------------------------------------------------------
RUN apt-get update && apt-get install -y --no-install-recommends \
        sumo sumo-tools sumo-doc \
        ffmpeg \
        libgl1-mesa-glx \
        libglib2.0-0 \
        xvfb x11vnc novnc websockify fluxbox \
        libgl1 libglib2.0-0 libsm6 libxext6 libxrender1 \
        libspatialindex-dev \
        curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .

# Install a CPU-only PyTorch build *before* ultralytics, otherwise pip pulls
# the much larger default CUDA build even on machines with no GPU.
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir torch torchvision --index-url https://download.pytorch.org/whl/cpu

RUN pip install --no-cache-dir -r requirements.txt \
    && pip install --no-cache-dir rtree

COPY app.py sumo_utils.py video_processor.py ./
COPY static ./static
COPY networks ./networks

RUN mkdir -p uploads outputs \
    && rm -f /tmp/.X99-lock

EXPOSE 8000 6080

# ---------------------------------------------------------------------------
# Startup sequence:
#   1. rm -f the X lock file so a crashed previous run can't block Xvfb.
#   2. Start Xvfb on :99 at 2560x1440 resolution.
#   3. Start Fluxbox window manager so noVNC renders a desktop environment instead of a blank frame.
#   4. Start x11vnc against display :99 on port 5900.
#   5. Start websockify/noVNC bridging browser websockets on port 6080.
#   6. Finally start the FastAPI app with uvicorn.
# ---------------------------------------------------------------------------
    CMD ["sh", "-c", "\
    rm -f /tmp/.X99-lock && \
    Xvfb :99 -screen 0 2560x1440x24 & \
    sleep 2 && \
    fluxbox & \
    x11vnc -display :99 -forever -shared -nopw -rfbport 5900 -listen 127.0.0.1 & \
    sleep 1 && \
    websockify --web=/usr/share/novnc/ 6080 127.0.0.1:5900 & \
    uvicorn app:app --host 0.0.0.0 --port 8000 \
"]