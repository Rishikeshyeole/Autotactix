# syntax=docker/dockerfile:1
FROM python:3.11-slim-bookworm

LABEL maintainer="AutoTactix"[cite: 3]
LABEL description="Smart Traffic Management & Simulation System — SUMO/TraCI + YOLOv8/Supervision"[cite: 3]

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    DISPLAY=:99 \
    LIBGL_ALWAYS_SOFTWARE=1 \
    QT_X11_NO_MITSHM=1 \
    SUMO_HOME=/usr/share/sumo \
    NOVNC_PORT=6080 \
    VNC_PORT=5900 \
    APP_PORT=8000[cite: 3]

# ---------------------------------------------------------------------------
# System dependencies:
#   sumo / sumo-tools / sumo-doc  -> SUMO + sumo-gui + $SUMO_HOME/tools (traci/sumolib source)
#   xvfb, x11vnc, fluxbox         -> virtual display + VNC server + window manager (prevents blank screen)
#   novnc, websockify             -> browser-accessible noVNC bridge on 6080
#   libgl1-mesa-dri, mesa-utils   -> Mesa software OpenGL drivers required for software rendering without GPU
#   dbus-x11                      -> D-Bus session support to prevent Qt/FOX GUI toolkits from crashing
#   libgl1, libglib2.0-0, libsm6, libxext6, libxrender1 -> required by OpenCV / Qt (sumo-gui) at runtime
#   libspatialindex-dev           -> backs the optional `rtree` package for fast edge lookups in sumolib
# ---------------------------------------------------------------------------
RUN apt-get update && apt-get install -y --no-install-recommends \
        sumo sumo-tools sumo-doc \
        ffmpeg \
        libgl1-mesa-glx \
        libgl1-mesa-dri \
        mesa-utils \
        dbus-x11 \
        libglib2.0-0 \
        xvfb x11vnc novnc websockify fluxbox \
        libgl1 libglib2.0-0 libsm6 libxext6 libxrender1 \
        libspatialindex-dev \
        curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*[cite: 3]

WORKDIR /app[cite: 3]

COPY requirements.txt .[cite: 3]

# Install a CPU-only PyTorch build *before* ultralytics, otherwise pip pulls
# the much larger default CUDA build even on machines with no GPU.
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir torch torchvision --index-url https://download.pytorch.org/whl/cpu[cite: 3]

RUN pip install --no-cache-dir -r requirements.txt \
    && pip install --no-cache-dir rtree[cite: 3]

COPY app.py sumo_utils.py video_processor.py ./[cite: 3]
COPY static ./static[cite: 3]
COPY networks ./networks[cite: 3]

RUN mkdir -p uploads outputs \
    && rm -f /tmp/.X99-lock /tmp/.X11-unix/X99[cite: 3]

EXPOSE 8000 6080[cite: 3]

# ---------------------------------------------------------------------------
# Robust startup sequence:
#   1. Clean stale X11 locks and socket files.
#   2. Start Xvfb virtual display on :99.
#   3. Wait synchronously until the /tmp/.X11-unix/X99 socket is created (eliminates race condition).
#   4. Initialize D-Bus environment for GUI stability.
#   5. Start Fluxbox window manager.
#   6. Launch sumo-gui in background via nohup (logs output to /tmp/sumo_gui.log).
#   7. Bind x11vnc to IPv4 127.0.0.1:5900.
#   8. Start websockify/noVNC on port 6080 targeting 127.0.0.1:5900.
#   9. Start FastAPI backend with uvicorn.
# ---------------------------------------------------------------------------
CMD ["sh", "-c", "\
    rm -f /tmp/.X99-lock /tmp/.X11-unix/X99 && \
    Xvfb :99 -screen 0 1920x1080x24 & \
    echo 'Waiting for Xvfb display socket...'; \
    while [ ! -e /tmp/.X11-unix/X99 ]; do sleep 0.2; done; \
    echo 'Xvfb display ready!'; \
    export DISPLAY=:99; \
    if command -v dbus-launch >/dev/null 2>&1; then eval $(dbus-launch --sh-syntax); fi; \
    fluxbox & \
    sleep 1; \
    nohup sumo-gui > /tmp/sumo_gui.log 2>&1 & \
    x11vnc -display :99 -forever -shared -nopw -rfbport 5900 -listen 127.0.0.1 & \
    sleep 1; \
    websockify --web=/usr/share/novnc/ 6080 127.0.0.1:5900 & \
    exec uvicorn app:app --host 0.0.0.0 --port 8000 \
"]