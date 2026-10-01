import sys
import os
import time
import json
import subprocess
import numpy as np
import mss
from PIL import Image
from constants import DEFAULT_STRATEGIC_ORDERS

HUD_STATE_PATH = "/home/user/Documents/foxhole/hud_state.json"
GAME_REGION = {"top": 0, "left": 1920, "width": 1920, "height": 1080}
MAP_SNAPSHOT_SHM = "/dev/shm/latest_map_snapshot.png"
MAP_SNAPSHOT_DISK = "/home/user/Documents/foxhole/latest_map.png"

class FoxholeContinuousAnalyzer:
    def __init__(self, target_fps=4):
        self.interval = 1.0 / target_fps
        self.running = True
        self.last_state_summary = ""
        self.was_map_open = False
        self.last_map_analysis_time = 0
        
    def detect_ui_state(self, frame):
        h, w, _ = frame.shape
        
        # 1. Map open detection
        # Center region luminance and color balance
        center = frame[h // 4 : 3 * h // 4, w // 4 : 3 * w // 4]
        # In BGRA, channels: 0:B, 1:G, 2:R
        mean_lum = float(np.mean(center[:, :, :3]))
        
        # Top-left melee/fist icon (hidden when map is open)
        fist_roi = frame[20:80, 20:80]
        white_pts = int(np.sum((fist_roi[:, :, 0] > 200) & (fist_roi[:, :, 1] > 200) & (fist_roi[:, :, 2] > 200)))
        
        # Map in Foxhole has parchment background (> 85 lum) and hides world weapon HUD (white_pts < 300)
        is_map = bool(white_pts < 300 and mean_lum > 85)
        
        # 2. Stockpile panel check (only relevant if not full map)
        stockpile_roi = frame[105:125, 700:750]
        stockpile_open = bool((not is_map) and (np.mean(stockpile_roi) > 40 and np.mean(stockpile_roi) < 180))
        
        # 3. Bleed / High Vignette detection
        corners = np.concatenate([
            frame[20:60, 20:60],
            frame[20:60, w-60:w-20],
            frame[h-60:h-20, 20:60],
            frame[h-60:h-20, w-60:w-20]
        ])
        mean_r = float(np.mean(corners[:, :, 2]))
        mean_b = float(np.mean(corners[:, :, 0]))
        mean_g = float(np.mean(corners[:, :, 1]))
        is_red_flashing = bool((not is_map) and (mean_r > 70) and (mean_r > (mean_b + mean_g) * 0.7))
        
        return {
            "map_open": is_map,
            "stockpile_visible": stockpile_open,
            "bleed_danger": is_red_flashing,
            "ambient_lum": round(mean_lum, 1)
        }

    def trigger_map_analysis(self, frame):
        """
        Asynchronously saves map snapshot to RAM disk and dispatches map worker.
        """
        now = time.time()
        if now - self.last_map_analysis_time < 3.0:
            return  # Cooldown
        self.last_map_analysis_time = now
        
        print("[Foxhole Analyzer] 🗺️ MAP OPENED! Capturing snapshot and launching async analysis...")
        
        # Convert BGRA buffer to RGB Image and save directly to /dev/shm
        rgb_frame = frame[:, :, [2, 1, 0]]
        img = Image.fromarray(rgb_frame)
        try:
            img.save(MAP_SNAPSHOT_SHM, format="PNG")
            img.save(MAP_SNAPSHOT_DISK, format="PNG")
        except Exception as e:
            print("Failed to save map snapshot:", e)
            
        # Update HUD alert immediately
        self.flash_map_alert()
        
        # Spawn map worker process detached
        cmd = [
            "python3",
            "/home/user/Documents/foxhole/map_analyzer_worker.py"
        ]
        subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def flash_map_alert(self):
        current = {}
        if os.path.exists(HUD_STATE_PATH):
            try:
                with open(HUD_STATE_PATH, "r") as f:
                    current = json.load(f)
            except Exception:
                pass
        current["active"] = True
        current["title"] = "WARDEN TACTICAL ASSISTANT // 🗺️ SCANNING MAP INTEL..."
        alerts = current.get("alerts", [])
        alerts = [{"text": "🗺️ MAP INTEL ACQUIRED — ANALYZING STRATEGIC PICTURE...", "color": [0, 240, 255]}] + alerts[:2]
        current["alerts"] = alerts
        
        tmp_path = HUD_STATE_PATH + ".tmp"
        with open(tmp_path, "w") as f:
            json.dump(current, f, indent=2)
        os.replace(tmp_path, HUD_STATE_PATH)

    def update_hud(self, state):
        current = {}
        if os.path.exists(HUD_STATE_PATH):
            try:
                with open(HUD_STATE_PATH, "r") as f:
                    current = json.load(f)
            except Exception:
                pass
                
        alerts = []
        if state["map_open"]:
            alerts.append({"text": "MAP ACTIVE: INSPECTING HEX & FRONTLINES", "color": [0, 240, 255]})
        else:
            alerts.append({"text": "DESTINATION: MARBAN HOLLOW FACTORY (IN QUEUE)", "color": [0, 220, 255]})
        
        if state["bleed_danger"]:
            alerts.append({"text": "CRITICAL: DAMAGE / BLEED DETECTED! NO MED AT BASE!", "color": [255, 30, 30]})
        else:
            alerts.append({"text": "HEALTH STATUS: NOMINAL — MAINTAIN DISTANCE", "color": [100, 255, 120]})
            
        if state["stockpile_visible"]:
            alerts.append({"text": "STOCKPILE DETECTED: CHECK PUBLIC CRATES FIRST", "color": [255, 200, 0]})
            
        current["active"] = True
        current["alerts"] = alerts
        if "strategic_orders" not in current or not current["strategic_orders"]:
            current["strategic_orders"] = DEFAULT_STRATEGIC_ORDERS
        
        tmp_path = HUD_STATE_PATH + ".tmp"
        with open(tmp_path, "w") as f:
            json.dump(current, f, indent=2)
        os.replace(tmp_path, HUD_STATE_PATH)

    def run(self):
        print(f"[Foxhole Analyzer] Initializing MSS capture pipeline (Target: {1.0/self.interval:.1f} Hz)...")
        with mss.MSS() as sct:
            while self.running:
                t0 = time.time()
                
                sct_img = sct.grab(GAME_REGION)
                frame = np.frombuffer(sct_img.raw, dtype=np.uint8).reshape((sct_img.height, sct_img.width, 4))
                
                state = self.detect_ui_state(frame)
                
                # Check for Map Open transition
                if state["map_open"] and not self.was_map_open:
                    self.trigger_map_analysis(frame)
                self.was_map_open = state["map_open"]
                
                summary = f"Map: {state['map_open']} | Stockpile: {state['stockpile_visible']} | Bleed: {state['bleed_danger']}"
                if summary != self.last_state_summary:
                    self.last_state_summary = summary
                    self.update_hud(state)
                    print(f"[{time.strftime('%H:%M:%S')}] {summary}")
                    
                elapsed = time.time() - t0
                sleep_time = self.interval - elapsed
                if sleep_time > 0:
                    time.sleep(sleep_time)

if __name__ == "__main__":
    analyzer = FoxholeContinuousAnalyzer(target_fps=4)
    try:
        analyzer.run()
    except KeyboardInterrupt:
        print("[Foxhole Analyzer] Stopped.")
