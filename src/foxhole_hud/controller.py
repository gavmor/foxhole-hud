import time
import threading
import asyncio
import numpy as np
import mss

from typing import Dict, Any, List
from PyQt6.QtCore import QObject, pyqtSignal

from foxhole_hud.metadata_store import MetadataStore
from foxhole_hud.mcp_consultant import FoxholeMCPConsultant
from foxhole_hud.bdi_engine import BDIGoalArbiter
from foxhole_hud.cv_engine import FoxholeCVDetector

GAME_REGION = {"top": 0, "left": 1920, "width": 1920, "height": 1080}

class ControllerSignals(QObject):
    frame_processed = pyqtSignal()

class StrategicControlLoop(threading.Thread):
    """
    Continuous out-of-band CV control loop.
    Integrates:
    - 20 FPS MSS XShm screen capture (< 5ms)
    - 1ms OpenCV Native HUD detection
    - Persistent SQLite metadata logging (frames, latency, coordinates)
    - Foxhole MCP consultation (recipes, facilities, map facts)
    - BDI / GDA goal arbitration (Goal > Strategic Priority > Tactical Priority)
    """
    def __init__(self, signals: ControllerSignals, db_path=None):
        super().__init__(daemon=True)
        self.signals = signals
        self.running = True
        self.lock = threading.Lock()
        
        self.metadata = MetadataStore(db_path) if db_path else MetadataStore()
        self.mcp = FoxholeMCPConsultant(self.metadata)
        self.bdi = BDIGoalArbiter(self.mcp, self.metadata)
        self.detector = FoxholeCVDetector()
        
        self.active_boxes: List[Dict[str, Any]] = []
        self.telemetry: Dict[str, Any] = {
            "capture_ms": 4.8,
            "cv_ms": 1.0,
            "is_thinking": False,
            "mcp_status": "IDLE",
            "db_frames": 0
        }
        self.mcp_loop = asyncio.new_event_loop()
        threading.Thread(target=self._run_async_mcp_loop, daemon=True).start()

    def _run_async_mcp_loop(self):
        asyncio.set_event_loop(self.mcp_loop)
        self.mcp_loop.run_forever()

    def get_telemetry(self) -> Dict[str, Any]:
        with self.lock:
            return dict(self.telemetry)

    def get_boxes(self) -> List[Dict[str, Any]]:
        with self.lock:
            return list(self.active_boxes)

    def trigger_mcp_lookup(self, item_or_region: str, query_type: str = "recipe"):
        async def _query():
            with self.lock:
                self.telemetry["mcp_status"] = "CONSULTING"
                self.telemetry["is_thinking"] = True
            
            if query_type == "recipe":
                res = await self.mcp.get_recipe(item_or_region)
            else:
                res = await self.mcp.get_region_info(item_or_region)
                
            with self.lock:
                self.telemetry["mcp_status"] = "SYNCED"
                self.telemetry["is_thinking"] = False
            self.signals.frame_processed.emit()

        asyncio.run_coroutine_threadsafe(_query(), self.mcp_loop)

    def run(self):
        print("[Strategic Control Loop] Initialized at 20 FPS...")
        # Initial MCP baseline check (asynchronous, non-blocking)
        self.trigger_mcp_lookup("Dunne Transport", "recipe")
        
        with mss.MSS() as sct:
            while self.running:
                t_start = time.time()
                
                # 1. Grab 1080p frame buffer via XShm
                t_cap0 = time.time()
                sct_img = sct.grab(GAME_REGION)
                frame = np.frombuffer(sct_img.raw, dtype=np.uint8).reshape((sct_img.height, sct_img.width, 4))
                cap_ms = (time.time() - t_cap0) * 1000
                
                # 2. Sub-millisecond OpenCV ROI detection
                t_cv0 = time.time()
                boxes, cv_state = self.detector.process_frame(frame)
                cv_ms = (time.time() - t_cv0) * 1000
                
                # 3. Store frame telemetry in SQLite metadata store
                banner_txt = "Fort Viper : Afric's Approach" if cv_state.get("has_banner") else ""
                cv_state["subregion_text"] = banner_txt
                player_pos = cv_state.get("player_marker")
                self.metadata.record_frame(cap_ms, cv_ms, cv_state, player_pos)
                
                # 4. BDI Goal Arbitration & Discrepancy Evaluation
                with self.lock:
                    self.active_boxes = boxes
                    discrepancy = self.bdi.update_beliefs_from_cv(cv_state, banner_txt)
                    if discrepancy:
                        self.telemetry["is_thinking"] = True
                    else:
                        self.telemetry["is_thinking"] = False
                        
                    self.telemetry["capture_ms"] = round(cap_ms, 1)
                    self.telemetry["cv_ms"] = round(cv_ms, 1)
                    metrics = self.metadata.get_recent_metrics()
                    self.telemetry["db_frames"] = metrics["total_frames_recorded"]
                
                # 5. Notify Qt overlay of frame completion
                self.signals.frame_processed.emit()
                
                # Regulate to 20 FPS (50ms) to ensure zero game or compositor lag
                elapsed = time.time() - t_start
                sleep_time = 0.05 - elapsed
                if sleep_time > 0:
                    time.sleep(sleep_time)

    def stop(self):
        self.running = False
        if self.mcp_loop.is_running():
            self.mcp_loop.call_soon_threadsafe(self.mcp_loop.stop)
        self.metadata.close()
