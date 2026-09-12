# syntax=docker/dockerfile:1
FROM python:3.11-slim-bookworm

LABEL maintainer="AutoTactix"
LABEL description="Smart Traffic Management & Simulation System — SUMO/TraCI + YOLOv8/Supervision"

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    DISPLAY=:99 \
    LIBGL_ALWAYS_SOFTWARE=1 \
    QT_X11_NO_MITSHM=1 \
    SUMO_HOME=/usr/share/sumo \
    NOVNC_PORT=6080 \
    VNC_PORT=5900 \
    APP_PORT=8000

# Install system GUI dependencies, software OpenGL rasterizer drivers, and window manager
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
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .

# Install CPU-only PyTorch and python packages
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir torch torchvision --index-url https://download.pytorch.org/whl/cpu

RUN pip install --no-cache-dir -r requirements.txt \
    && pip install --no-cache-dir rtree

COPY app.py sumo_utils.py video_processor.py ./
COPY static ./static
COPY entrypoint.sh /entrypoint.sh

RUN mkdir -p uploads outputs \
    && chmod +x /entrypoint.sh \
    && rm -f /tmp/.X99-lock /tmp/.X11-unix/X99

EXPOSE 8000 6080

ENTRYPOINT ["/entrypoint.sh"]
