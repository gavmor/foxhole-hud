import cv2
import numpy as np

class FoxholeCVDetector:
    """
    Pure local, out-of-band OpenCV detection engine.
    Zero disk I/O, zero LLM calls. Sub-millisecond ROI classification.
    """
    def __init__(self):
        # Static baseline anchor ROIs for standard 1080p Foxhole HUD
        self.roi_stamina = [8, 14, 180, 130]      # Top-left stance & stamina
        self.roi_compass = [1765, 15, 1900, 145]  # Top-right compass
        self.roi_squads = [1665, 305, 1905, 640]  # Mid-right squad panel
        self.roi_chat = [1360, 645, 1905, 935]    # Bottom-right chat panel
        self.roi_shield = [930, 765, 990, 840]    # Center-bottom vehicle shield
        self.roi_banner = [540, 660, 1380, 735]   # Center subregion banner
        
    def process_frame(self, bgra_frame):
        """
        Takes raw BGRA frame from MSS buffer (1080, 1920, 4).
        Returns active detected HUD bounding boxes and inferred tactical state.
        """
        # Convert to BGR for OpenCV
        bgr = bgra_frame[:, :, :3]
        h, w, _ = bgr.shape
        
        detected_boxes = []
        tactical_state = {
            "is_map": False,
            "in_vehicle": False,
            "has_banner": False,
            "has_queue": False,
            "is_bleeding": False,
            "subregion_text": "",
            "player_marker": None
        }
        
        # 1. Map Open Detection (Parchment check)
        center_crop = bgr[h // 4 : 3 * h // 4, w // 4 : 3 * w // 4]
        mean_lum = float(np.mean(center_crop))
        
        fist_crop = bgr[20:80, 20:80]
        white_pts = int(np.sum((fist_crop[:, :, 0] > 200) & (fist_crop[:, :, 1] > 200) & (fist_crop[:, :, 2] > 200)))
        
        if white_pts < 250 and mean_lum > 85:
            tactical_state["is_map"] = True
            # Detect player chevron on map (vibrant orange: R>200, 90<G<170, B<80)
            mask_player = (bgr[:, :, 2] > 200) & (bgr[:, :, 1] > 90) & (bgr[:, :, 1] < 170) & (bgr[:, :, 0] < 80)
            pts = np.argwhere(mask_player)
            if len(pts) >= 15:
                py, px = np.mean(pts, axis=0)
                tactical_state["player_marker"] = (int(px), int(py))
                detected_boxes.append({
                    "box": [int(px) - 24, int(py) - 24, int(px) + 24, int(py) + 24],
                    "label": "PLAYER POSITION (GPS CHEVRON)",
                    "color": (255, 140, 0),
                    "tag_pos": "top"
                })
            return detected_boxes, tactical_state

        # 2. Bleed / Vignette Check
        corners = np.concatenate([
            bgr[20:60, 20:60], bgr[20:60, w-60:w-20],
            bgr[h-60:h-20, 20:60], bgr[h-60:h-20, w-60:w-20]
        ])
        mean_b, mean_g, mean_r = np.mean(corners, axis=(0, 1))
        if mean_r > 70 and mean_r > (mean_b + mean_g) * 0.7:
            tactical_state["is_bleeding"] = True

        # 3. Native HUD Bounding Boxes (When in World View)
        # A. Stance & Stamina (Always on HUD in world)
        detected_boxes.append({
            "box": self.roi_stamina,
            "label": "STANCE & STAMINA METER",
            "color": (0, 255, 200),
            "tag_pos": "bottom"
        })
        
        # B. Compass (Top-right)
        detected_boxes.append({
            "box": self.roi_compass,
            "label": "COMPASS & WIND AZIMUTH",
            "color": (255, 200, 0),
            "tag_pos": "bottom"
        })
        
        # C. Squads Panel (Mid-right)
        detected_boxes.append({
            "box": self.roi_squads,
            "label": "REGIONAL SQUADS",
            "color": (255, 100, 255),
            "tag_pos": "top"
        })
        
        # D. Chat Window (Bottom-right)
        detected_boxes.append({
            "box": self.roi_chat,
            "label": "CHAT LOG & COMMS",
            "color": (0, 220, 255),
            "tag_pos": "top"
        })
        
        # E. Vehicle Shield Check (around x: 930..990, y: 765..840)
        shield_crop = bgr[765:840, 930:990]
        # In vehicle, the shield icon has a distinct light grey/white outline
        shield_edges = cv2.Canny(shield_crop, 50, 150)
        if np.sum(shield_edges > 0) > 120:
            tactical_state["in_vehicle"] = True
            detected_boxes.append({
                "box": self.roi_shield,
                "label": "VEHICLE STATUS / ARMOR",
                "color": (255, 80, 80),
                "tag_pos": "top"
            })
            
        # F. Subregion Banner Detection (Banner appears when entering new territory)
        banner_crop = bgr[660:735, 540:1380]
        # Text characters inside banner have high contrast white pixels on dark gradient
        white_banner_pts = np.sum((banner_crop[:, :, 0] > 190) & (banner_crop[:, :, 1] > 190) & (banner_crop[:, :, 2] > 190))
        if white_banner_pts > 450:
            tactical_state["has_banner"] = True
            detected_boxes.append({
                "box": self.roi_banner,
                "label": "SUBREGION TRANSITION BANNER",
                "color": (50, 255, 100),
                "tag_pos": "top"
            })

        return detected_boxes, tactical_state
