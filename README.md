# Foxhole Strategic HUD & Out-of-Band CV Control Loop

A transparent, click-through strategic overlay HUD for Foxhole powered by a sub-millisecond local OpenCV computer vision engine, Belief-Desire-Intention (BDI) / Goal-Driven Autonomy (GDA) arbitration, and integration with the Foxhole MediaWiki MCP server.

Runs completely out-of-band at 20 FPS with **zero LLM tokens during the live control loop**.

---

## Key Features

1. **Sub-Millisecond 5-Mode CV Classification (< 2 ms)**
   - **`PEDESTRIAN`**: Grounded in solid sprint stamina bar meter (`> 1000 px`).
   - **`VEHICLE`**: Silhouette seat/cargo status widget and vehicle armor status.
   - **`SPECTATING`**: Bounded top-center spectator banner text on dark background.
   - **`DEPLOY_MAP`**: World Deployment / Conquest directory sidebar with casualties panel.
   - **`MAP` ('M')**: Full-screen tactical parchment canvas with GPS chevron tracking.

2. **3-Tier Grounded Goal Hierarchy**
   - **Campaign Goal (Macro)**: Theater-wide operational objective.
   - **Strategic Priority (Hex)**: Subregion tactical mandate (e.g. Seaport fuel crisis).
   - **Tactical Priority (Micro)**: Immediate surroundings guidance (Refinery haul, medic call, spawn selection).

3. **Pixel-Perfect Native HUD Bounding Boxes**
   - Minimap (Bottom-Left: `[0, 756, 324, 1079]`)
   - Stance & Stamina Meter (Top-Left: `[16, 16, 155, 142]`)
   - Compass & Azimuth (Top-Right: `[1775, 18, 1895, 138]`)
   - Regional Squads (Mid-Right: `[1670, 310, 1905, 703]`)
   - Comms & Chat Log (Bottom-Right: `[1376, 703, 1905, 1033]`)

4. **Hardware-Accelerated Click-Through Transparent HUD**
   - Built with PyQt6 with `Qt.WindowTransparentForInput` and `WA_TranslucentBackground`.
   - Real-time telemetry badges: Capture latency (ms), BDI state, MCP consultation status, and SQLite recorded frames.

---

## Architecture

```
[ Foxhole Game Window (HDMI-0 1920x1080) ]
                   │
                   ▼ (20 FPS MSS XShm grab)
       [ Local CV Engine (< 2ms) ]
                   │
       ┌───────────┴───────────┐
       ▼                       ▼
 [ Mode Classifier ]   [ ROI Extractors ]
       │                       │
       ▼                       ▼
[ BDI Goal Arbiter ]   [ Bounding Boxes ]
       │                       │
       └───────────┬───────────┘
                   ▼
  [ Transparent PyQt6 Click-Through HUD ]
```

---

## Installation & Setup

Requirements:
- Linux X11 display
- Python 3.12+
- `uv` package manager

```bash
# Clone the repository
git clone git@github.com:gavmor/foxhole-hud.git
cd foxhole-hud

# Install dependencies
uv sync
```

---

## Running the HUD Daemon

```bash
# Launch the supervisor process
DISPLAY=:0 XAUTHORITY=~/.Xauthority uv run python main.py
```

Process uses single-instance locking via `/dev/shm/foxhole_hud.pid`.

---

## Running Tests

All 5 operational modes are verified against real in-game screenshot fixtures in `tests/fixtures/`:

```bash
uv run pytest -v
```

```text
tests/test_control_loop.py::test_metadata_store_lifecycle PASSED
tests/test_control_loop.py::test_bdi_goal_arbitration_hierarchy PASSED
tests/test_control_loop.py::test_mcp_consultation PASSED
tests/test_control_loop.py::test_cv_engine_submillisecond_roi PASSED
tests/test_control_loop.py::test_five_mode_instant_recognition PASSED
tests/test_mode_recognition_fixtures.py::test_all_game_mode_fixtures[pedestrian.png-PEDESTRIAN] PASSED
tests/test_mode_recognition_fixtures.py::test_all_game_mode_fixtures[vehicle.png-VEHICLE] PASSED
tests/test_mode_recognition_fixtures.py::test_all_game_mode_fixtures[spectating.png-SPECTATING] PASSED
tests/test_mode_recognition_fixtures.py::test_all_game_mode_fixtures[deploy_map.png-DEPLOY_MAP] PASSED
tests/test_mode_recognition_fixtures.py::test_all_game_mode_fixtures[map.png-MAP] PASSED

============================== 10 passed in 1.65s ==============================
```

---

## License

MIT
