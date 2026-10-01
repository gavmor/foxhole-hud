import time
from PyQt6.QtCore import Qt, QRectF, QPointF
from PyQt6.QtWidgets import QWidget
from PyQt6.QtGui import QPainter, QColor, QFont, QPen, QBrush

class StrategicOverlayHUD(QWidget):
    """
    Hardware-accelerated transparent click-through HUD overlay.
    Displays:
    - Background Telemetry Badges ('CAPTURED', 'THINKING', 'MCP SYNC')
    - 3-Tier Goal Hierarchy: Goal > Strategic Priority > Tactical Priority
    - Native Foxhole HUD Bounding Boxes
    """
    def __init__(self, controller):
        super().__init__()
        self.controller = controller
        
        flags = (
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.WindowTransparentForInput |
            Qt.WindowType.Tool |
            Qt.WindowType.X11BypassWindowManagerHint
        )
        self.setWindowFlags(flags)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setGeometry(1920, 0, 1920, 1080)
        
        self.font_title = QFont("DejaVu Sans", 9, QFont.Weight.Bold)
        self.font_body = QFont("DejaVu Sans", 8, QFont.Weight.Bold)
        self.font_mono = QFont("DejaVu Sans Mono", 8, QFont.Weight.Bold)
        self.font_roi = QFont("DejaVu Sans", 8, QFont.Weight.Bold)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        telemetry = self.controller.get_telemetry()
        summary = self.controller.get_player_summary() if hasattr(self.controller, "get_player_summary") else telemetry.get("summary", {})
        boxes = self.controller.get_boxes()

        # -------------------------------------------------------------
        # 1. TOP TELEMETRY STATUS BAR (MODE / CAP / CV / FPS / DB / TRANSITIONS)
        # -------------------------------------------------------------
        bar_w = 880
        bar_h = 30
        bar_x = (1920 - bar_w) // 2
        bar_y = 12
        
        # Container box
        painter.setPen(QPen(QColor(50, 130, 220, 220), 1.5))
        painter.setBrush(QBrush(QColor(10, 15, 24, 230)))
        painter.drawRoundedRect(QRectF(bar_x, bar_y, bar_w, bar_h), 5, 5)
        
        # A. Operational Mode Badge
        mode = summary.get("current_mode", telemetry.get("mode", "PEDESTRIAN"))
        if mode == "DEPLOY_MAP":
            mode_col = QColor(255, 215, 0)
            mode_text = "DEPLOY MAP"
        elif mode == "MAP":
            mode_col = QColor(0, 220, 255)
            mode_text = "MAP ('M')"
        elif mode == "VEHICLE":
            mode_col = QColor(255, 150, 0)
            mode_text = "VEHICLE"
        elif mode == "SPECTATING":
            mode_col = QColor(255, 100, 100)
            mode_text = "SPECTATING"
        else:
            mode_col = QColor(0, 255, 180)
            mode_text = "PEDESTRIAN"

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(mode_col))
        painter.drawEllipse(QPointF(bar_x + 14, bar_y + 15), 4, 4)
        
        painter.setFont(self.font_mono)
        painter.setPen(mode_col)
        painter.drawText(bar_x + 24, bar_y + 19, f"MODE: {mode_text}")
        
        # B. Captured & CV Latency Badge
        perf = summary.get("performance", {})
        cap_ms = perf.get("avg_capture_ms", telemetry.get("capture_ms", 4.8))
        cv_ms = perf.get("avg_cv_ms", telemetry.get("cv_ms", 1.0))
        pipe_ms = perf.get("total_pipeline_ms", cap_ms + cv_ms)
        max_fps = perf.get("max_possible_fps", 1000.0 / max(1.0, pipe_ms))

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(QColor(0, 255, 120)))
        painter.drawEllipse(QPointF(bar_x + 200, bar_y + 15), 4, 4)
        painter.setPen(QColor(230, 245, 255))
        painter.drawText(bar_x + 210, bar_y + 19, f"CAP: {cap_ms:.1f}ms  CV: {cv_ms:.1f}ms")

        # C. Effective Capacity FPS
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(QColor(80, 200, 255)))
        painter.drawEllipse(QPointF(bar_x + 400, bar_y + 15), 4, 4)
        painter.setPen(QColor(100, 210, 255))
        painter.drawText(bar_x + 410, bar_y + 19, f"CAPACITY: {max_fps:.0f} FPS")
        
        # D. Metadata DB Frames
        db_count = telemetry.get("db_frames", 0)
        painter.setFont(self.font_mono)
        painter.setPen(QColor(170, 190, 210))
        painter.drawText(bar_x + 590, bar_y + 19, f"DB: {db_count} FRAMES")

        # E. Transitions Count
        analytics = summary.get("analytics", {})
        trans_count = analytics.get("transition_count", telemetry.get("total_transitions", 0))
        painter.setPen(QColor(255, 200, 100))
        painter.drawText(bar_x + 750, bar_y + 19, f"SHIFTS: {trans_count}")

        # -------------------------------------------------------------
        # 2. REAL-TIME PLAYER STATUS & TELEMETRY MONITOR (Top-Left: x=20, y=172)
        # -------------------------------------------------------------
        panel_x = 20
        panel_y = 172
        panel_w = 600
        panel_h = 248
        
        # Panel Shell
        painter.setPen(QPen(QColor(40, 130, 230, 220), 1.5))
        painter.setBrush(QBrush(QColor(12, 17, 26, 245)))
        painter.drawRoundedRect(QRectF(panel_x, panel_y, panel_w, panel_h), 6, 6)
        
        # Top banner accent strip
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(mode_col))
        painter.drawRoundedRect(QRectF(panel_x + 1, panel_y + 1, panel_w - 2, 4), 2, 2)
        
        # Header Title & Active Mode
        painter.setFont(self.font_title)
        painter.setPen(QColor(90, 190, 255))
        painter.drawText(panel_x + 14, panel_y + 24, "PLAYER STATUS & TELEMETRY MONITOR")
        
        session_str = summary.get("session_time_formatted", "00:00")
        painter.setFont(self.font_mono)
        painter.setPen(mode_col)
        painter.drawText(panel_x + panel_w - 180, panel_y + 24, f"[{mode_text}] {session_str}")
        
        painter.setPen(QPen(QColor(35, 75, 120, 180), 1))
        painter.drawLine(panel_x + 14, panel_y + 32, panel_x + panel_w - 14, panel_y + 32)

        vitals = summary.get("vitals", {})
        nav = summary.get("navigation", {})

        # --- SECTION 1: PHYSICAL VITALS & STAMINA ---
        painter.setFont(QFont("DejaVu Sans", 7, QFont.Weight.Bold))
        painter.setPen(QColor(140, 180, 220))
        painter.drawText(panel_x + 14, panel_y + 46, "PHYSICAL VITALS & POSTURE:")

        # Left: Health & Bleeding
        is_bleed = vitals.get("is_bleeding", False)
        health_col = QColor(255, 60, 60) if is_bleed else QColor(0, 255, 160)
        health_text = "● CRITICAL (BLEEDING)" if is_bleed else "● STABLE"
        painter.setFont(self.font_mono)
        painter.setPen(health_col)
        painter.drawText(panel_x + 14, panel_y + 64, f"HEALTH: {health_text}")

        # Stance & Armor
        stance = vitals.get("stance", "STAND")
        has_shield = vitals.get("has_shield", False)
        armor_text = "ARMORED" if has_shield else "NONE"
        painter.setPen(QColor(220, 235, 250))
        painter.drawText(panel_x + 14, panel_y + 82, f"STANCE: {stance:<7}  ARMOR: {armor_text}")

        # Right: Stamina Bar & Trend
        stam_pct = max(0, min(100, vitals.get("stamina_pct", 100)))
        stam_trend = vitals.get("stamina_trend", "STABLE")
        
        if stam_trend == "DRAINING":
            trend_col = QColor(255, 160, 40)
        elif stam_trend == "RECOVERING":
            trend_col = QColor(0, 220, 255)
        elif stam_trend == "FULL":
            trend_col = QColor(0, 255, 160)
        else:
            trend_col = QColor(200, 210, 225)

        painter.setFont(self.font_mono)
        painter.setPen(trend_col)
        painter.drawText(panel_x + 310, panel_y + 64, f"STAMINA: {stam_pct}% [{stam_trend}]")

        # Stamina meter visual bar
        bar_gauge_x = panel_x + 310
        bar_gauge_y = panel_y + 72
        bar_gauge_w = 260
        bar_gauge_h = 10
        painter.setPen(QPen(QColor(30, 50, 75), 1))
        painter.setBrush(QBrush(QColor(15, 25, 38)))
        painter.drawRoundedRect(QRectF(bar_gauge_x, bar_gauge_y, bar_gauge_w, bar_gauge_h), 2, 2)

        fill_w = int(bar_gauge_w * (stam_pct / 100.0))
        if fill_w > 0:
            if stam_pct > 50:
                bar_fill_col = QColor(0, 230, 160)
            elif stam_pct > 20:
                bar_fill_col = QColor(255, 200, 50)
            else:
                bar_fill_col = QColor(255, 70, 70)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(bar_fill_col))
            painter.drawRoundedRect(QRectF(bar_gauge_x + 1, bar_gauge_y + 1, fill_w - 2, bar_gauge_h - 2), 2, 2)

        # Divider line
        painter.setPen(QPen(QColor(35, 75, 120, 140), 1))
        painter.drawLine(panel_x + 14, panel_y + 94, panel_x + panel_w - 14, panel_y + 94)

        # --- SECTION 2: SPATIAL POSITION & ODOMETER ---
        painter.setFont(QFont("DejaVu Sans", 7, QFont.Weight.Bold))
        painter.setPen(QColor(140, 180, 220))
        painter.drawText(panel_x + 14, panel_y + 108, "NAVIGATION & ODOMETER:")

        gps = nav.get("gps_coord")
        if gps:
            gps_text = f"FIX: X={gps[0]} Y={gps[1]} (MAP LOCK)"
            gps_col = QColor(255, 215, 0)
        else:
            gps_text = "STANDBY (PRESS 'M' TO LOCATE CHEVRON)"
            gps_col = QColor(140, 160, 185)

        minimap_active = nav.get("has_minimap", False)
        minimap_text = "ACTIVE" if minimap_active else "INACTIVE"
        minimap_col = QColor(0, 255, 180) if minimap_active else QColor(140, 160, 185)

        painter.setFont(self.font_mono)
        painter.setPen(gps_col)
        painter.drawText(panel_x + 14, panel_y + 126, f"GPS {gps_text}")

        dist_px = nav.get("cumulative_dist_px", 0.0)
        painter.setPen(QColor(220, 235, 250))
        painter.drawText(panel_x + 14, panel_y + 144, f"ODOMETER: {dist_px:,.0f} px traversed")

        painter.setPen(minimap_col)
        painter.drawText(panel_x + 360, panel_y + 144, f"LOCAL MINIMAP: {minimap_text}")

        # Divider line
        painter.setPen(QPen(QColor(35, 75, 120, 140), 1))
        painter.drawLine(panel_x + 14, panel_y + 156, panel_x + panel_w - 14, panel_y + 156)

        # --- SECTION 3: SESSION MODE DISTRIBUTION ---
        painter.setFont(QFont("DejaVu Sans", 7, QFont.Weight.Bold))
        painter.setPen(QColor(140, 180, 220))
        painter.drawText(panel_x + 14, panel_y + 170, "SESSION MODE ALLOCATION:")

        mode_pcts = analytics.get("mode_percentages", {})
        
        # Segmented mode allocation bar
        dist_bar_x = panel_x + 14
        dist_bar_y = panel_y + 178
        dist_bar_w = panel_w - 28
        dist_bar_h = 10

        painter.setPen(QPen(QColor(30, 50, 75), 1))
        painter.setBrush(QBrush(QColor(15, 25, 38)))
        painter.drawRoundedRect(QRectF(dist_bar_x, dist_bar_y, dist_bar_w, dist_bar_h), 2, 2)

        cur_x = dist_bar_x + 1
        mode_palette = {
            "PEDESTRIAN": QColor(0, 255, 180),
            "VEHICLE": QColor(255, 150, 0),
            "MAP": QColor(0, 220, 255),
            "DEPLOY_MAP": QColor(255, 215, 0),
            "SPECTATING": QColor(255, 100, 100)
        }
        for m_name in ("PEDESTRIAN", "VEHICLE", "MAP", "DEPLOY_MAP", "SPECTATING"):
            pct = mode_pcts.get(m_name, 0.0)
            if pct > 0:
                seg_w = (pct / 100.0) * (dist_bar_w - 2)
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(QBrush(mode_palette.get(m_name, QColor(180, 180, 180))))
                painter.drawRect(QRectF(cur_x, dist_bar_y + 1, seg_w, dist_bar_h - 2))
                cur_x += seg_w

        # Percentage legend
        painter.setFont(self.font_mono)
        ped_p = mode_pcts.get("PEDESTRIAN", 0.0)
        veh_p = mode_pcts.get("VEHICLE", 0.0)
        map_p = mode_pcts.get("MAP", 0.0)
        dep_p = mode_pcts.get("DEPLOY_MAP", 0.0)
        spec_p = mode_pcts.get("SPECTATING", 0.0)
        
        dist_legend = f"PED: {ped_p:.1f}% | VEH: {veh_p:.1f}% | MAP: {map_p:.1f}% | DEP: {dep_p:.1f}% | SPEC: {spec_p:.1f}%"
        painter.setPen(QColor(190, 215, 235))
        painter.drawText(panel_x + 14, panel_y + 204, dist_legend)

        # Performance summary line
        painter.setPen(QColor(120, 180, 220))
        painter.drawText(panel_x + 14, panel_y + 224, f"LATENCY: CAP {cap_ms:.1f}ms + CV {cv_ms:.1f}ms = {pipe_ms:.1f}ms (~{max_fps:.0f} FPS CAPACITY)")

        # -------------------------------------------------------------
        # 3. DRAW NATIVE HUD BOUNDING BOXES
        # -------------------------------------------------------------
        for b in boxes:
            bx0, by0, bx1, by1 = b["box"]
            rgb = b["color"]
            col = QColor(rgb[0], rgb[1], rgb[2])
            
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(QColor(rgb[0], rgb[1], rgb[2], 20)))
            painter.drawRect(bx0, by0, bx1 - bx0, by1 - by0)
            
            painter.setPen(QPen(col, 1.5))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(bx0, by0, bx1 - bx0, by1 - by0)
            
            # Corner brackets
            c_len = 10
            painter.setPen(QPen(col, 2.5))
            painter.drawLine(bx0, by0, bx0 + c_len, by0)
            painter.drawLine(bx0, by0, bx0, by0 + c_len)
            painter.drawLine(bx1, by0, bx1 - c_len, by0)
            painter.drawLine(bx1, by0, bx1, by0 + c_len)
            painter.drawLine(bx0, by1, bx0 + c_len, by1)
            painter.drawLine(bx0, by1, bx0, by1 - c_len)
            painter.drawLine(bx1, by1, bx1 - c_len, by1)
            painter.drawLine(bx1, by1, bx1, by1 - c_len)
            
            # Label Tag
            lbl = b["label"]
            painter.setFont(self.font_roi)
            tw = painter.fontMetrics().horizontalAdvance(lbl) + 14
            th = 18
            
            tag_y = by1 + 4 if b.get("tag_pos") == "bottom" else by0 - th - 4
            if tag_y < 10:
                tag_y = by1 + 4
            tag_x = bx0
            if tag_x + tw > 1910:
                tag_x = 1910 - tw
                
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(QColor(12, 16, 24, 230)))
            painter.drawRoundedRect(QRectF(tag_x, tag_y, tw, th), 3, 3)
            painter.setPen(col)
            painter.drawText(QRectF(tag_x + 6, tag_y, tw - 12, th), int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft), lbl)
