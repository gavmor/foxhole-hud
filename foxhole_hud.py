import sys
import os
import json
from PyQt6.QtCore import Qt, QTimer, QRectF, QPointF
from PyQt6.QtWidgets import QApplication, QWidget
from PyQt6.QtGui import QPainter, QColor, QFont, QPen, QBrush

STATE_FILE = "/home/user/Documents/foxhole/hud_state.json"

class TransparentHUD(QWidget):
    def __init__(self):
        super().__init__()
        
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
        
        # HDMI-0 (Right Monitor) 1920x1080 at +1920+0
        self.setGeometry(1920, 0, 1920, 1080)
        
        self.state = {}
        self.last_mtime = 0
        self.load_state()
        
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.check_state_file)
        self.timer.start(250)

    def check_state_file(self):
        if os.path.exists(STATE_FILE):
            mtime = os.path.getmtime(STATE_FILE)
            if mtime != self.last_mtime:
                self.load_state()
                self.update()

    def load_state(self):
        try:
            if os.path.exists(STATE_FILE):
                with open(STATE_FILE, "r") as f:
                    self.state = json.load(f)
                self.last_mtime = os.path.getmtime(STATE_FILE)
        except Exception as e:
            print("Error loading HUD state:", e)

    def paintEvent(self, event):
        if not self.state.get("active", True):
            return
            
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # -------------------------------------------------------------
        # 1. STRATEGIC ORDERS PANEL (Top-Left, x=24, y=24)
        # -------------------------------------------------------------
        strat = self.state.get("strategic_orders")
        if strat:
            panel_x = 24
            panel_y = 24
            panel_w = 460
            
            directives = strat.get("directives", [])
            panel_h = 75 + len(directives) * 24
            
            # Panel Background
            painter.setPen(QPen(QColor(50, 140, 230, 220), 1.5))
            painter.setBrush(QBrush(QColor(12, 18, 28, 230)))
            painter.drawRoundedRect(QRectF(panel_x, panel_y, panel_w, panel_h), 6, 6)
            
            # Top accent bar
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(QColor(50, 140, 230)))
            painter.drawRoundedRect(QRectF(panel_x + 1, panel_y + 1, panel_w - 2, 4), 2, 2)
            
            # Title
            painter.setFont(QFont("DejaVu Sans", 10, QFont.Weight.Bold))
            painter.setPen(QColor(100, 190, 255))
            header_title = strat.get("title", "STRATEGIC ORDERS")
            painter.drawText(QRectF(panel_x + 16, panel_y + 12, panel_w - 32, 20), int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft), header_title)
            
            # Mission Subtitle
            painter.setFont(QFont("DejaVu Sans", 9, QFont.Weight.Bold))
            painter.setPen(QColor(240, 245, 255))
            mission_title = strat.get("mission", "")
            painter.drawText(QRectF(panel_x + 16, panel_y + 32, panel_w - 32, 18), int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft), mission_title)
            
            # Divider line
            painter.setPen(QPen(QColor(40, 80, 130, 180), 1))
            painter.drawLine(panel_x + 16, panel_y + 54, panel_x + panel_w - 16, panel_y + 54)
            
            # Directives Checklist
            dy = panel_y + 62
            for d in directives:
                status = d.get("status", "PENDING")
                text = d.get("text", "")
                
                if status == "DONE":
                    icon_str = "[✓]"
                    icon_color = QColor(0, 240, 120)
                    text_color = QColor(160, 190, 180)
                elif status == "IN_PROGRESS":
                    icon_str = "[▶]"
                    icon_color = QColor(255, 200, 40)
                    text_color = QColor(255, 235, 170)
                else:
                    icon_str = "[ ]"
                    icon_color = QColor(140, 160, 180)
                    text_color = QColor(210, 220, 230)
                
                painter.setFont(QFont("DejaVu Sans Mono", 9, QFont.Weight.Bold))
                painter.setPen(icon_color)
                painter.drawText(panel_x + 16, dy + 14, icon_str)
                
                painter.setFont(QFont("DejaVu Sans", 8, QFont.Weight.Bold))
                painter.setPen(text_color)
                painter.drawText(QRectF(panel_x + 46, dy, panel_w - 60, 20), int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft), text)
                
                dy += 24

        # -------------------------------------------------------------
        # 2. TOP CENTER HUD & LIVE ALERTS
        # -------------------------------------------------------------
        header_text = self.state.get("title", "WARDEN TACTICAL HUD")
        painter.setFont(QFont("DejaVu Sans", 10, QFont.Weight.Bold))
        
        hw, hh = 440, 30
        hx = (1920 - hw) // 2
        hy = 12
        
        painter.setPen(QPen(QColor(60, 140, 240, 220), 1.5))
        painter.setBrush(QBrush(QColor(12, 18, 26, 210)))
        painter.drawRoundedRect(QRectF(hx, hy, hw, hh), 5, 5)
        
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(QColor(0, 255, 120)))
        painter.drawEllipse(QPointF(hx + 16, hy + 15), 4, 4)
        
        painter.setPen(QColor(230, 240, 255))
        painter.drawText(QRectF(hx + 28, hy, hw - 36, hh), int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft), header_text)
        
        alerts = self.state.get("alerts", [])
        ay = 48
        for alert in alerts:
            txt = alert.get("text", "")
            rgb = alert.get("color", [255, 255, 255])
            col = QColor(rgb[0], rgb[1], rgb[2])
            
            painter.setFont(QFont("DejaVu Sans", 9, QFont.Weight.Bold))
            tw = painter.fontMetrics().horizontalAdvance(txt) + 24
            ax = (1920 - tw) // 2
            
            painter.setPen(QPen(col, 1))
            painter.setBrush(QBrush(QColor(10, 15, 22, 220)))
            painter.drawRoundedRect(QRectF(ax, ay, tw, 24), 4, 4)
            
            painter.setPen(col)
            painter.drawText(QRectF(ax + 12, ay, tw - 24, 24), int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignCenter), txt)
            ay += 28

        # -------------------------------------------------------------
        # 3. CUSTOM BOXES
        # -------------------------------------------------------------
        boxes = self.state.get("boxes", [])
        for b in boxes:
            bx, by, bw, bh = b["x"], b["y"], b["w"], b["h"]
            rgb = b.get("color", [0, 200, 255])
            alpha = b.get("alpha", 200)
            col = QColor(rgb[0], rgb[1], rgb[2], alpha)
            
            painter.setPen(QPen(col, 2))
            painter.setBrush(QBrush(QColor(rgb[0], rgb[1], rgb[2], 25)))
            painter.drawRoundedRect(QRectF(bx, by, bw, bh), 4, 4)
            
            lbl = b.get("label", "")
            if lbl:
                painter.setFont(QFont("DejaVu Sans", 9, QFont.Weight.Bold))
                lw = painter.fontMetrics().horizontalAdvance(lbl) + 16
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(QBrush(QColor(rgb[0], rgb[1], rgb[2], 220)))
                painter.drawRoundedRect(QRectF(bx, by - 22, lw, 20), 3, 3)
                painter.setPen(QColor(0, 0, 0))
                painter.drawText(QRectF(bx + 8, by - 22, lw, 20), int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft), lbl)

def main():
    os.environ["DISPLAY"] = ":0"
    os.environ["XAUTHORITY"] = "/home/user/.Xauthority"
    app = QApplication(sys.argv)
    hud = TransparentHUD()
    hud.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
