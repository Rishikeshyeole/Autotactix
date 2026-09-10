#!/bin/bash
set -e

# 1. Start Xvfb Virtual Framebuffer on DISPLAY :99
Xvfb :99 -screen 0 1920x1080x24 &
export DISPLAY=:99

# 2. Start Fluxbox Window Manager (renders the desktop UI)
fluxbox &

# 3. Start x11vnc Server on port 5900
x11vnc -display :99 -forever -shared -nopw -rfbport 5900 &

# 4. Start noVNC Websockify Bridge on port 6080
websockify --web /usr/share/novnc 6080 localhost:5900 &

# 5. Start FastAPI Backend Application
exec python3 app.py
