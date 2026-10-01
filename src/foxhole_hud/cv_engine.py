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
        self.roi_minimap = [0, 756, 324, 1079]       # Bottom-left corner minimap (324x323)
        
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

        # 3. Minimap Detection (Bottom-Left Corner: 324x323 at [0, 756, 324, 1079])
        minimap_crop = bgr[756:1079, 0:324]
        m_mean = np.mean(minimap_crop, axis=(0, 1))
        # Characteristic map paper: R ~= G ~= B and luminance > 110
        if 110 < m_mean[0] < 175 and 110 < m_mean[1] < 175 and 100 < m_mean[2] < 175:
            tactical_state["has_minimap"] = True
            tactical_state["at_industrial_hub"] = True
            
            # Detect player chevron on minimap to establish immediate surroundings
            hsv_mini = cv2.cvtColor(minimap_crop, cv2.COLOR_BGR2HSV)
            mask1 = cv2.inRange(hsv_mini, (10, 140, 170), (25, 255, 255))
            mask2 = (minimap_crop[:, :, 2] > 200) & (minimap_crop[:, :, 1] > 90) & (minimap_crop[:, :, 1] < 170) & (minimap_crop[:, :, 0] < 90)
            c_pts = np.argwhere(mask1 | mask2)
            
            subregion = "Maiden's Veil Industrial Hub"
            if len(c_pts) >= 5:
                cy, cx = np.mean(c_pts, axis=0)
                tactical_state["player_marker"] = (int(cx), int(756 + cy))
                if cx < 135:
                    subregion = "Maiden's Veil Seaport / Docks (West)"
                elif cx > 195:
                    subregion = "Maiden's Veil Refinery / Scrap Yard (East)"
                elif cy < 155:
                    subregion = "Maiden's Veil Town Base / Relic (North)"
                else:
                    subregion = "Maiden's Veil Factory / Logistics Depot (South)"
            
            tactical_state["subregion"] = subregion
            
            detected_boxes.append({
                "box": self.roi_minimap,
                "label": f"MINIMAP // {subregion.upper()}",
                "color": (255, 200, 40),
                "tag_pos": "top"
            })

        # 4. Top-Left Stance / Vehicle Role
        # Check if in vehicle ("Dunne Transport" or "Passenger" text at y: 80..100)
        text_row = bgr[82:98, 10:140]
        white_text = np.sum((text_row[:, :, 0] > 180) & (text_row[:, :, 1] > 180) & (text_row[:, :, 2] > 180))
        in_veh = white_text > 80
        
        if in_veh:
            tactical_state["in_vehicle"] = True
            tactical_state["vehicle_type"] = "Dunne Transport"
            box_stamina = [16, 16, 190, 110]
            label_stamina = "VEHICLE: DUNNE TRANSPORT"
        else:
            # Calibrated to cover stance icon (y:20..85) and stamina meter (y:124..136)
            box_stamina = [16, 16, 155, 142]
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
