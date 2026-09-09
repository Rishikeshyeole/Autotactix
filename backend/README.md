# AutoTactix — Smart Traffic Management & Simulation System

A single web dashboard with two independent traffic-engineering tools:

- **Module 1 — SUMO simulation.** Enter a start/end GPS coordinate pair, pick
  a SUMO network, and watch a live `sumo-gui` run streamed into the browser
  over noVNC while a vehicle flow is injected between the matched road edges.
- **Module 2 — AI video traffic analysis.** Upload a traffic-camera clip,
  draw lane polygons and/or counting lines on the extracted first frame, and
  get back an annotated output video plus per-lane occupancy, counting-line
  crossings, and vehicle-class totals (YOLOv8 + ByteTrack + Supervision).

The two modules are intentionally independent — Module 2 does not require
SUMO, and Module 1 does not require a GPU or a video file.

## Quick start (Docker)

```bash

```

Then open **http://localhost:8000**. The live SUMO stream (once a simulation
is running) is proxied through **http://localhost:6080**, but you don't need
to open that URL directly — the dashboard embeds it in an iframe.

A synthetic ~850 m two-edge network, `networks/sample_toy_network.net.xml`,
ships pre-loaded so "Run simulation" works immediately with the pre-filled
coordinates — it is a smoke-test fixture, not a real road network. To
simulate a real area, export a network from SUMO's
[OSM Web Wizard](https://sumo.dlr.de/docs/Tools/Import/OSM.html) (or
`netconvert` with a `--proj.*` option so it keeps a geo-projection) and
upload the resulting `.net.xml` from the dashboard, or drop it into
`networks/` before starting the container.

## Running without Docker

You'll need SUMO installed separately (`apt install sumo sumo-tools` on
Debian/Ubuntu, or the installer from sumo.dlr.de on other platforms) with
`sumo-gui` on your `PATH`, plus Xvfb/x11vnc/websockify if you want the noVNC
stream outside of Docker. Module 2 (video analysis) has no such requirement
and will run entirely with the pip dependencies below.

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
# CPU-only PyTorch avoids a multi-GB CUDA download if you don't have a GPU:
pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu
uvicorn app:app --host 0.0.0.0 --port 8000 --reload
```

Then open http://localhost:8000. Module 1 will report a clear error if
`sumo-gui` isn't found, rather than crashing — you can still use Module 2.

## Project layout

```
app.py               FastAPI server: routes for both modules, job registries
sumo_utils.py         Module 1: coordinate conversion, edge matching, TraCI run loop
video_processor.py    Module 2: frame extraction, YOLOv8 + Supervision pipeline
static/index.html     Dashboard UI (Tailwind + vanilla JS, no build step)
networks/             .net.xml files available to Module 1 (uploadable at runtime)
uploads/              Uploaded videos (created at runtime)
outputs/               Extracted frames + processed output videos (created at runtime)
Dockerfile            Single-container image: SUMO + Xvfb/noVNC + the FastAPI app
docker-compose.yml    Port mapping, volumes, healthcheck
requirements.txt      Pinned Python dependencies
```

## API reference

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/networks` | List available `.net.xml` files |
| POST | `/api/networks/upload` | Upload a new network file |
| POST | `/api/simulate` | Start a simulation run (returns a `job_id` immediately) |
| GET | `/api/simulate/{job_id}` | Poll status: `starting` → `running` → `finished`/`error` |
| POST | `/api/simulate/{job_id}/stop` | Stop the running simulation |
| POST | `/api/extract-first-frame` | Upload a video, get back frame 0 as a data URL |
| POST | `/api/analyze-video` | Submit lane annotations, start processing (returns a `job_id`) |
| GET | `/api/analyze-video/{job_id}` | Poll status + progress + metrics + output video URL |

Only one simulation can run at a time (there's a single virtual display), and
`/api/simulate` returns `409 Conflict` if you try to start a second one while
one is active.

## Design notes & things that were fixed along the way

A few details worth knowing about if you extend this:

- **Coordinate conversion.** The correct sumolib method is
  `Net.convertLonLat2XY(lon, lat)` — note the argument order (longitude
  first) and that it requires the network to have geo-projection info
  (`net.hasGeoProj()`). Networks without a `<location projParameter="...">`
  (e.g. ones built without `--proj.*`) will raise a clear error instead of
  silently producing wrong coordinates.
- **Edge matching** searches progressively wider radii (10 m → 250 m) and
  only considers edges that allow `passenger` vehicles, so a click near a
  sidewalk-only edge doesn't get matched.
- **TraCI cleanup** is idempotent and runs both before a new simulation
  starts and in a `finally` block, so a crashed run can't block the next one
  from launching `sumo-gui` again on the same display.
- **Canvas coordinate scaling.** The browser reports clicks in the `<canvas>`
  element's own pixel buffer size; `video_processor.scale_coordinates()`
  rescales those into the source video's native resolution before building
  `supervision.PolygonZone` / `LineZone` objects, so annotation still lines
  up correctly even if the canvas is ever displayed at a different size than
  the source video.
- **`ultralytics` + CPU-only PyTorch.** `pip install ultralytics` pulls the
  full CUDA build of PyTorch by default even without a GPU, ballooning the
  image by several GB. The Dockerfile installs the CPU wheel first; see the
  comments there (and in `docker-compose.yml`) for how to switch to GPU
  inference instead.
- **Only one direct YOLO model is loaded**, lazily, and cached across
  requests (`video_processor._get_model()`), so repeated `/analyze-video`
  calls don't reload `yolov8n.pt` every time. Swap the `MODEL_WEIGHTS`
  constant to use a different checkpoint (including newer YOLO26 weights,
  which `ultralytics` also loads).

## Known limitations

- Single-writer concurrency: one SUMO run and one video-analysis job at a
  time are what the in-memory job registries and the single Xvfb display are
  designed for. For multi-user concurrent access, move the job store to
  Redis/a database and run multiple video-worker containers behind a queue.
- The noVNC stream has no authentication (`x11vnc -nopw`) by design for
  local/trusted-network use. Put it behind your own auth layer (a reverse
  proxy, VPN, etc.) before exposing port 6080 or 8000 publicly.
- Vehicle classification is limited to what YOLO's COCO-pretrained weights
  recognize: car, motorcycle, bus, truck. Auto-rickshaws/tempos common on
  Indian roads will generally be classified as the closest COCO class
  (car or motorcycle) rather than their own category — training or
  fine-tuning a custom model is the way to add a dedicated class.
