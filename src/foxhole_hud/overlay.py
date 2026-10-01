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
        intentions = self.controller.bdi.current_intentions
        boxes = self.controller.get_boxes()

        # -------------------------------------------------------------
        # 1. TOP TELEMETRY STATUS BAR (MODE / CAPTURED / THINKING / MCP / DB)
        # -------------------------------------------------------------
        bar_w = 800
        bar_h = 30
        bar_x = (1920 - bar_w) // 2
        bar_y = 12
        
        # Container box
        painter.setPen(QPen(QColor(50, 130, 220, 220), 1.5))
        painter.setBrush(QBrush(QColor(10, 15, 24, 230)))
        painter.drawRoundedRect(QRectF(bar_x, bar_y, bar_w, bar_h), 5, 5)
        
        # A. Operational Mode Badge
        mode = telemetry.get("mode", "PEDESTRIAN")
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
        
        # B. Captured Badge
        cap_ms = telemetry.get("capture_ms", 4.8)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(QColor(0, 255, 120)))
        painter.drawEllipse(QPointF(bar_x + 190, bar_y + 15), 4, 4)
        
        painter.setPen(QColor(230, 245, 255))
        painter.drawText(bar_x + 200, bar_y + 19, f"CAP: {cap_ms:.1f}ms")
        
        # C. Thinking Badge (BDI / GDA Engine)
        is_thinking = telemetry.get("is_thinking", False)
        think_col = QColor(255, 190, 0) if is_thinking else QColor(80, 180, 255)
        think_text = "THINKING" if is_thinking else "EVALUATING"
        
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(think_col))
        painter.drawEllipse(QPointF(bar_x + 340, bar_y + 15), 4, 4)
        
        painter.setPen(think_col)
        painter.drawText(bar_x + 350, bar_y + 19, think_text)
        
        # D. MCP Consultation Status
        mcp_status = telemetry.get("mcp_status", "IDLE")
        mcp_col = QColor(0, 230, 255) if mcp_status == "CONSULTING" else QColor(140, 160, 190)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(mcp_col))
        painter.drawEllipse(QPointF(bar_x + 480, bar_y + 15), 4, 4)
        
        painter.setPen(mcp_col)
        painter.drawText(bar_x + 490, bar_y + 19, f"MCP: {mcp_status}")
        
        # E. Metadata DB Count
        db_count = telemetry.get("db_frames", 0)
        painter.setFont(self.font_mono)
        painter.setPen(QColor(170, 190, 210))
        painter.drawText(bar_x + 630, bar_y + 19, f"DB: {db_count} FRAMES")

        # -------------------------------------------------------------
        # 2. THREE-TIER GOAL HIERARCHY CARD (Top-Left: x=20, y=172)
        # -------------------------------------------------------------
        panel_x = 20
        panel_y = 172
        panel_w = 580
        panel_h = 196
        
        # Panel Shell
        painter.setPen(QPen(QColor(40, 130, 230, 220), 1.5))
        painter.setBrush(QBrush(QColor(12, 17, 26, 240)))
        painter.drawRoundedRect(QRectF(panel_x, panel_y, panel_w, panel_h), 6, 6)
        
        # Top banner strip
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(mode_col))
        painter.drawRoundedRect(QRectF(panel_x + 1, panel_y + 1, panel_w - 2, 4), 2, 2)
        
        # Header Title
        painter.setFont(self.font_title)
        painter.setPen(QColor(90, 180, 255))
        painter.drawText(panel_x + 14, panel_y + 24, f"STRATEGIC CONTROL LOOP // {mode}")
        
        painter.setPen(QPen(QColor(35, 75, 120, 180), 1))
        painter.drawLine(panel_x + 14, panel_y + 32, panel_x + panel_w - 14, panel_y + 32)
        
        # Tier 1: GOAL (Macro / Campaign)
        painter.setFont(QFont("DejaVu Sans", 7, QFont.Weight.Bold))
        painter.setPen(QColor(140, 180, 220))
        painter.drawText(panel_x + 14, panel_y + 46, "[1] CAMPAIGN GOAL (MACRO // LIVE CONQUEST):")
        
        painter.setFont(self.font_body)
        painter.setPen(QColor(245, 250, 255))
        painter.drawText(QRectF(panel_x + 14, panel_y + 50, panel_w - 28, 20), int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft), intentions.goal)
        
        # Tier 2: STRATEGIC PRIORITY (Theater / Hex)
        painter.setFont(QFont("DejaVu Sans", 7, QFont.Weight.Bold))
        painter.setPen(QColor(255, 190, 40))
        painter.drawText(panel_x + 14, panel_y + 80, "[2] STRATEGIC PRIORITY (THEATER MANDATE):")
        
        painter.setFont(self.font_body)
        painter.setPen(QColor(255, 240, 190))
        painter.drawText(QRectF(panel_x + 14, panel_y + 84, panel_w - 28, 28), int(Qt.TextFlag.TextWordWrap | Qt.AlignmentFlag.AlignLeft), intentions.strategic_priority)
        
        # Tier 3: TACTICAL PRIORITY (Immediate Surroundings / Micro)
        painter.setFont(QFont("DejaVu Sans", 7, QFont.Weight.Bold))
        painter.setPen(QColor(0, 240, 140))
        painter.drawText(panel_x + 14, panel_y + 122, "[3] TACTICAL PRIORITY (IMMEDIATE PHYSICAL SURROUNDINGS):")
        
        painter.setFont(self.font_body)
        painter.setPen(QColor(200, 255, 230))
        painter.drawText(QRectF(panel_x + 14, panel_y + 128, panel_w - 28, 56), int(Qt.TextFlag.TextWordWrap | Qt.AlignmentFlag.AlignLeft), intentions.tactical_priority)

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
