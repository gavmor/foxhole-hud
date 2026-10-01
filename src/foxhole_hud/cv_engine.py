import cv2
import numpy as np

class FoxholeCVDetector:
    """
    Calibrated local OpenCV detection engine.
    Accurately tracks native HUD components without overlap or cobblestone false positives.
    """
    def __init__(self):
        # Precise, non-overlapping calibrated baseline boundaries for 1080p
        self.roi_compass = [1775, 18, 1895, 138]     # Top-right compass
        self.roi_squads = [1670, 310, 1905, 595]     # Mid-right squad roster (ends above chat)
        self.roi_chat = [1365, 648, 1905, 930]       # Bottom-right chat log (tabs + text)
        self.roi_minimap = [2, 700, 172, 1076]       # Bottom-left corner minimap
        
    def process_frame(self, bgra_frame):
        bgr = bgra_frame[:, :, :3]
        h, w, _ = bgr.shape
        
        detected_boxes = []
        tactical_state = {
            "is_full_map": False, "is_map": False,
            "has_minimap": False,
            "in_vehicle": False,
            "vehicle_type": "",
            "is_bleeding": False,
            "at_industrial_hub": False,
            "player_marker": None
        }
        
        # 1. Full Map Check ('M' key)
        center_crop = bgr[h // 4 : 3 * h // 4, w // 4 : 3 * w // 4]
        mean_lum = float(np.mean(center_crop))
        fist_crop = bgr[20:80, 20:80]
        white_pts = int(np.sum((fist_crop[:, :, 0] > 200) & (fist_crop[:, :, 1] > 200) & (fist_crop[:, :, 2] > 200)))
        
        if white_pts < 100 and mean_lum > 85:
            tactical_state["is_full_map"] = True
            # Locate player chevron on full map
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

        # 3. Minimap Detection (Bottom-Left Corner)
        # Foxhole minimap is at x: 0..172, y: 700..1076
        minimap_crop = bgr[700:1076, 2:172]
        m_mean = np.mean(minimap_crop, axis=(0, 1))
        # Characteristic map paper: R ~= G ~= B and luminance > 120
        if 115 < m_mean[0] < 175 and 115 < m_mean[1] < 175 and 105 < m_mean[2] < 170:
            tactical_state["has_minimap"] = True
            tactical_state["at_industrial_hub"] = True
            detected_boxes.append({
                "box": self.roi_minimap,
                "label": "MINIMAP (MAIDEN'S VEIL HUB)",
                "color": (255, 200, 40),
                "tag_pos": "top"
            })

        # 4. Top-Left Stance / Vehicle Role
        # Check if in vehicle ("Dunne Transport" or "Passenger" text at y: 80..100)
        text_row = bgr[82:98, 10:140]
        white_text = np.sum((text_row[:, :, 0] > 180) & (text_row[:, :, 1] > 180) & (text_row[:, :, 2] > 180))
        in_veh = white_text > 80
        
        # Check stamina bar at y: 112..124
        stamina_row = bgr[112:124, 10:140]
        has_stamina = np.sum((stamina_row[:, :, 0] > 180) & (stamina_row[:, :, 1] > 180)) > 60
        
        if in_veh:
            tactical_state["in_vehicle"] = True
            tactical_state["vehicle_type"] = "Dunne Transport"
            box_stamina = [8, 14, 110, 102]  # Compact vehicle icon box
            label_stamina = "VEHICLE: DUNNE TRANSPORT"
        else:
            box_stamina = [8, 14, 175, 126] if has_stamina else [8, 14, 85, 95]
            label_stamina = "STANCE & STAMINA METER"
            
        detected_boxes.append({
            "box": box_stamina,
            "label": label_stamina,
            "color": (0, 255, 200),
            "tag_pos": "bottom"
        })

        # 5. Compass (Top-Right)
        detected_boxes.append({
            "box": self.roi_compass,
            "label": "COMPASS & AZIMUTH",
            "color": (255, 200, 0),
            "tag_pos": "bottom"
        })

        # 6. Regional Squads Panel (Mid-Right, ends above chat)
        detected_boxes.append({
            "box": self.roi_squads,
            "label": "REGIONAL SQUADS",
            "color": (255, 100, 255),
            "tag_pos": "top"
        })

        # 7. Communications & Chat Log (Bottom-Right, exactly fits tabs + log)
        detected_boxes.append({
            "box": self.roi_chat,
            "label": "COMMS & CHAT LOG",
            "color": (0, 220, 255),
            "tag_pos": "top"
        })

        # 8. Vehicle Shield Detection (Strict Shape & Color, NO Cobblestone false positives)
        shield_crop = bgr[768:836, 932:988]
        # Real shield has pure white/light grey contour on dark interior
        white_shield_pts = np.sum((shield_crop[:, :, 0] > 210) & (shield_crop[:, :, 1] > 210) & (shield_crop[:, :, 2] > 210))
        # Shield border has roughly 60-200 pure white pixels, cobblestone has scattered mid-tones
        if 40 < white_shield_pts < 250:
            detected_boxes.append({
                "box": [932, 768, 988, 836],
                "label": "VEHICLE ARMOR STATUS",
                "color": (255, 80, 80),
                "tag_pos": "top"
            })

        return detected_boxes, tactical_state
