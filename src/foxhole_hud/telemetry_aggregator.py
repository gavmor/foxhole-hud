import time
import math
from collections import deque
from typing import Dict, Any, List, Optional, Tuple

class PlayerTelemetryAggregator:
    """
    Lightning-fast, zero-overhead real-time player status aggregator.
    Maintains:
    - Current Physical Vitals: Health, bleeding, stamina gauge (%), stance, armor.
    - Navigation: GPS map coordinates, minimap status, compass tracking.
    - Session Analytics: Session duration, mode time distribution (seconds & %),
      transition event logging, and cumulative distance traversed.
    """
    def __init__(self):
        self.session_start = time.time()
        self.last_update = time.time()
        
        # Mode tracking & distribution
        self.current_mode = "PEDESTRIAN"
        self.mode_start_time = time.time()
        self.mode_durations: Dict[str, float] = {
            "PEDESTRIAN": 0.0,
            "VEHICLE": 0.0,
            "SPECTATING": 0.0,
            "MAP": 0.0,
            "DEPLOY_MAP": 0.0
        }
        self.transitions: List[Tuple[float, str, str, float]] = [] # (timestamp, from, to, duration)
        
        # Physical vitals
        self.is_bleeding: bool = False
        self.stamina_pct: int = 100
        self.stamina_history: deque = deque(maxlen=20)
        self.stance: str = "STAND"
        self.has_shield: bool = False
        self.has_minimap: bool = False
        
        # Spatial navigation
        self.last_gps_fix: Optional[Tuple[int, int]] = None
        self.gps_history: deque = deque(maxlen=100)
        self.cumulative_distance_px: float = 0.0
        
        # Performance rollups
        self.capture_latencies: deque = deque(maxlen=40)
        self.cv_latencies: deque = deque(maxlen=40)

    def update(self, cv_state: Dict[str, Any], cap_ms: float, cv_ms: float) -> Dict[str, Any]:
        now = time.time()
        dt = now - self.last_update
        self.last_update = now
        
        # 1. Update Mode Duration & Transition
        new_mode = cv_state.get("mode", "PEDESTRIAN")
        if new_mode != self.current_mode:
            duration_in_prev = now - self.mode_start_time
            if self.current_mode in self.mode_durations:
                self.mode_durations[self.current_mode] += duration_in_prev
            self.transitions.append((now, self.current_mode, new_mode, duration_in_prev))
            self.current_mode = new_mode
            self.mode_start_time = now
        else:
            if self.current_mode in self.mode_durations:
                self.mode_durations[self.current_mode] += dt
                
        # 2. Physical Vitals
        self.is_bleeding = cv_state.get("is_bleeding", False)
        if new_mode == "PEDESTRIAN":
            if "stamina_pct" in cv_state:
                self.stamina_pct = cv_state["stamina_pct"]
                self.stamina_history.append((now, self.stamina_pct))
            if "stance" in cv_state and cv_state["stance"] != "N/A":
                self.stance = cv_state["stance"]
        elif new_mode == "VEHICLE":
            self.stance = "MOUNTED"
            
        self.has_shield = cv_state.get("has_shield", False)
        self.has_minimap = cv_state.get("has_minimap", False)
        
        # 3. Spatial & Distance
        marker = cv_state.get("player_marker")
        if marker:
            mx, my = marker
            if self.last_gps_fix:
                dist = math.hypot(mx - self.last_gps_fix[0], my - self.last_gps_fix[1])
                # Filter out map zoom/pan jumps (> 250px per frame)
                if 2.0 < dist < 250.0:
                    self.cumulative_distance_px += dist
            self.last_gps_fix = (mx, my)
            self.gps_history.append((now, mx, my))
            
        # 4. Latency
        self.capture_latencies.append(cap_ms)
        self.cv_latencies.append(cv_ms)
        
        return self.get_summary()

    def get_summary(self) -> Dict[str, Any]:
        now = time.time()
        session_elapsed = max(1.0, now - self.session_start)
        
        # Include current active mode duration in computation
        active_time = dict(self.mode_durations)
        if self.current_mode in active_time:
            active_time[self.current_mode] += (now - self.mode_start_time)
            
        total_time = sum(active_time.values()) or session_elapsed
        mode_percentages = {
            m: round((t / total_time) * 100, 1) for m, t in active_time.items()
        }
        
        # Stamina Trend
        if len(self.stamina_history) >= 5:
            delta_stamina = self.stamina_history[-1][1] - self.stamina_history[0][1]
            if delta_stamina < -5:
                stamina_trend = "DRAINING"
            elif delta_stamina > 5:
                stamina_trend = "RECOVERING"
            elif self.stamina_pct > 95:
                stamina_trend = "FULL"
            else:
                stamina_trend = "STABLE"
        else:
            stamina_trend = "FULL" if self.stamina_pct > 95 else "STABLE"
            
        avg_cap = sum(self.capture_latencies) / len(self.capture_latencies) if self.capture_latencies else 4.0
        avg_cv = sum(self.cv_latencies) / len(self.cv_latencies) if self.cv_latencies else 1.0
        effective_fps = 1000.0 / max(1.0, (avg_cap + avg_cv))
        
        mins = int(session_elapsed // 60)
        secs = int(session_elapsed % 60)
        time_formatted = f"{mins:02d}:{secs:02d}"
        
        return {
            "current_mode": self.current_mode,
            "session_time_formatted": time_formatted,
            "session_seconds": round(session_elapsed, 1),
            "vitals": {
                "health": "CRITICAL (BLEEDING)" if self.is_bleeding else "STABLE",
                "is_bleeding": self.is_bleeding,
                "stamina_pct": self.stamina_pct,
                "stamina_trend": stamina_trend,
                "stance": self.stance,
                "has_shield": self.has_shield
            },
            "navigation": {
                "has_minimap": self.has_minimap,
                "gps_coord": self.last_gps_fix,
                "cumulative_dist_px": round(self.cumulative_distance_px, 1)
            },
            "analytics": {
                "mode_percentages": mode_percentages,
                "transition_count": len(self.transitions),
                "recent_transitions": self.transitions[-5:]
            },
            "performance": {
                "avg_capture_ms": round(avg_cap, 1),
                "avg_cv_ms": round(avg_cv, 1),
                "total_pipeline_ms": round(avg_cap + avg_cv, 1),
                "max_possible_fps": round(effective_fps, 0)
            }
        }
