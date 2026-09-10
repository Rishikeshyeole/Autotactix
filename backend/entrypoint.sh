#!/bin/bash

# Clean up stale display lock files from previous runs
rm -f /tmp/.X99-lock /tmp/.X11-unix/X99

# 1. Start Xvfb Virtual Display
Xvfb :99 -screen 0 1920x1080x24 &

# Wait until Xvfb socket is active before launching dependent GUI services
echo "Waiting for Xvfb display socket..."
while [ ! -e /tmp/.X11-unix/X99 ]; do
    sleep 0.2
done
echo "Xvfb display ready!"

export DISPLAY=:99

# 2. Launch D-Bus session daemon (prevents Qt/SUMO GUI crashes)
if command -v dbus-launch >/dev/null 2>&1; then
    eval $(dbus-launch --sh-syntax)
fi

# 3. Start Fluxbox Window Manager
fluxbox &
sleep 1

# 4. Start SUMO GUI in background
nohup sumo-gui > /tmp/sumo_gui.log 2>&1 &

# 5. Start x11vnc and noVNC WebSocket bridge
x11vnc -display :99 -forever -shared -nopw -rfbport 5900 -listen 127.0.0.1 &
sleep 1
websockify --web=/usr/share/novnc/ 6080 127.0.0.1:5900 &

# 6. Launch FastAPI server
exec uvicorn app:app --host 0.0.0.0 --port 8000