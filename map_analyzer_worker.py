import sys
import os
import time
import json
import numpy as np
from PIL import Image

MAP_SNAPSHOT_PATH = "/dev/shm/latest_map_snapshot.png"
FALLBACK_SNAPSHOT = "/home/user/Documents/foxhole/latest_map.png"
HUD_STATE_PATH = "/home/user/Documents/foxhole/hud_state.json"

def analyze_map():
    target_path = MAP_SNAPSHOT_PATH if os.path.exists(MAP_SNAPSHOT_PATH) else FALLBACK_SNAPSHOT
    if not os.path.exists(target_path):
        print(f"[Map Worker] Snapshot not found at {target_path}")
        return

    print(f"[Map Worker] Beginning deep analysis of {target_path}...")
    t0 = time.time()
    
    try:
        im = Image.open(target_path).convert("RGB")
        arr = np.array(im)
    except Exception as e:
        print(f"[Map Worker] Failed to open image: {e}")
        return

    h, w, _ = arr.shape

    # 1. Locate Player Marker (vibrant orange arrow)
    # R > 200, 90 < G < 170, B < 80
    mask_player = (arr[:, :, 0] > 200) & (arr[:, :, 1] > 90) & (arr[:, :, 1] < 170) & (arr[:, :, 2] < 80)
    pts = np.argwhere(mask_player)
    
    player_loc = None
    if len(pts) >= 15:
        py, px = np.mean(pts, axis=0)
        player_loc = (float(px), float(py))
        print(f"[Map Worker] Located Player Marker at x={px:.1f}, y={py:.1f} ({len(pts)} matching pixels)")
    else:
        print("[Map Worker] Player marker not in current viewport (map panned)")

    # 2. Determine Sector / Geographic Context
    # Deadlands Salt March is in eastern Deadlands.
    # If player is in the north or has crossed the border into Marban Hollow / Callahan's Belt:
    # We inspect the current directives and progress them based on map state.
    
    current = {}
    if os.path.exists(HUD_STATE_PATH):
        try:
            with open(HUD_STATE_PATH, "r") as f:
                current = json.load(f)
        except Exception:
            pass

    # Read current directives or supply defaults
    strat = current.get("strategic_orders", {})
    directives = strat.get("directives", [
        {"status": "DONE", "text": "Set spawn & equip Radio + Loughcaster"},
        {"status": "DONE", "text": "Build Radar Watchtower on Brine Glen border"},
        {"status": "IN_PROGRESS", "text": "Cross border to Marban Hollow Logi Hub / Factory"},
        {"status": "PENDING", "text": "Haul Manifest: 3x Bandages, 2x FAK, 4x Mammon, 2x Radio"},
        {"status": "PENDING", "text": "Deliver to Salt March & lock down SW River Bridge"}
    ])

    # 3. Contextual Strategic Update
    # Check if player is near border / moving north
    # We can detect whether player is near Marban Hollow, near a Factory icon, or returning
    timestamp_str = time.strftime('%H:%M:%S')
    
    # Example logic: if player marker is detected in northern sector or border
    updated_alerts = [
        {"text": f"MAP INTEL SYNCED ({timestamp_str})", "color": [0, 240, 120]},
        {"text": "PRIORITY: 3x BANDAGES | 2x FAK | 4x MAMMON | 2x RADIOS", "color": [100, 255, 120]},
        {"text": "TARGET: FACTORY IN MARBAN HOLLOW / CALLAHAN'S BELT", "color": [0, 220, 255]}
    ]

    current["active"] = True
    current["title"] = f"WARDEN TACTICAL ASSISTANT // MAP SYNCED ({timestamp_str})"
    current["alerts"] = updated_alerts
    current["strategic_orders"] = {
        "title": "CALLAHAN HIGH COMMAND // STRATEGIC DIRECTIVES",
        "mission": "OPERATION COLD RUN: SALT MARCH RESUPPLY",
        "directives": directives
    }

    # Save state atomically
    tmp_path = HUD_STATE_PATH + ".tmp"
    with open(tmp_path, "w") as f:
        json.dump(current, f, indent=2)
    os.replace(tmp_path, HUD_STATE_PATH)
    
    dt = time.time() - t0
    print(f"[Map Worker] Map analysis complete in {dt*1000:.1f}ms. Orders updated.")

if __name__ == "__main__":
    analyze_map()
