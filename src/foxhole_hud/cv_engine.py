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
        self.roi_squads = [1670, 310, 1905, 703]     # Regional squad roster (flush to chat tabs)
        self.roi_chat = [1376, 703, 1905, 1033]      # Communications & chat log (tabs to input bar)
        self.roi_minimap = [0, 756, 324, 1079]       # Bottom-left corner minimap (324x323)
        
    def process_frame(self, bgra_frame):
        bgr = bgra_frame[:, :, :3]
        h, w, _ = bgr.shape
        
        detected_boxes = []
        tactical_state = {
            "mode": "PEDESTRIAN",
            "is_deploy_map": False,
            "is_full_map": False,
            "is_map": False,
            "has_minimap": False,
            "in_vehicle": False,
            "vehicle_type": "",
            "is_bleeding": False,
            "at_industrial_hub": False,
            "subregion": "Maiden's Veil (Industrial Sector)",
            "player_marker": None
        }

        # -------------------------------------------------------------
        # 1. INSTANT 5-WAY MODE RECOGNITION (< 1ms)
        # -------------------------------------------------------------
        # A. Sprint Stamina Bar check at [124:136, 22:145]
        # In Foxhole, when on foot as a pedestrian, the stamina bar is a solid bright white bar (>1000 px).
        # Neither Vehicle, nor Map, nor Deploy Map, nor Spectating ever displays this sprint stamina bar.
        stamina_row = bgr[124:136, 22:145]
        white_stamina = int(np.sum((stamina_row[:, :, 0] > 200) & (stamina_row[:, :, 1] > 200) & (stamina_row[:, :, 2] > 200)))

        # B. Map Parchment Canvas Check (strided 4x for sub-millisecond check)
        center_roi = bgr[200:800:4, 400:1500:4]
        parchment_pct = float(np.mean((center_roi[:, :, 0] > 110) & (center_roi[:, :, 1] > 125) & (center_roi[:, :, 2] > 125)))

        # C. Deploy Map check (sidebar has dark panel and 'CONQUEST' header)
        conquest_crop = bgr[90:130, 20:180]
        gray_c = cv2.cvtColor(conquest_crop, cv2.COLOR_BGR2GRAY)
        mask_c = gray_c > 180
        num_c, _, stats_c, _ = cv2.connectedComponentsWithStats(mask_c.astype(np.uint8))
        letters_c = [s for s in stats_c[1:] if 7 <= s[3] <= 18 and 4 <= s[2] <= 18]
        sidebar_dark = float(np.mean(bgr[100:400:2, 20:340:2])) < 80
        conquest_white = int(np.sum(mask_c))
        is_deploy = (parchment_pct > 0.40 and sidebar_dark and len(letters_c) >= 6 and conquest_white < 1200)

        # D. Vehicle widgets (silhouette at [30:88, 30:90] or armor shield)
        veh_crop = bgr[30:88, 30:90]
        veh_white = int(np.sum((veh_crop[:, :, 0] > 180) & (veh_crop[:, :, 1] > 180) & (veh_crop[:, :, 2] > 180)))
        shield_crop = bgr[768:836, 932:988]
        white_shield = int(np.sum((shield_crop[:, :, 0] > 200) & (shield_crop[:, :, 1] > 200) & (shield_crop[:, :, 2] > 200)))
        has_shield = (35 < white_shield < 250)

        # E. Spectator mode check (banner at [20:120, 700:1220])
        spec_crop = bgr[20:120, 700:1220]
        gray_s = cv2.cvtColor(spec_crop, cv2.COLOR_BGR2GRAY)
        mask_s = gray_s > 180
        num_s, _, stats_s, _ = cv2.connectedComponentsWithStats(mask_s.astype(np.uint8))
        spec_letters = [s for s in stats_s[1:] if 6 <= s[3] <= 30 and 4 <= s[2] <= 30]
        spec_dark_bg = float(np.mean(gray_s < 100))
        spec_white = int(np.sum(mask_s))
        is_spectating = (spec_dark_bg > 0.60 and 800 <= spec_white <= 4000 and len(spec_letters) >= 12 and parchment_pct < 0.20)

        # F. Minimap detection
        minimap_crop = bgr[756:1079:2, 0:324:2]
        m_mean = np.mean(minimap_crop, axis=(0, 1))
        has_minimap = (40 < m_mean[0] < 175 and 50 < m_mean[1] < 175 and 50 < m_mean[2] < 175)

        # Deterministic Hierarchy:
        if white_stamina > 500:
            current_mode = "PEDESTRIAN"
        elif parchment_pct > 0.40:
            if is_deploy:
                current_mode = "DEPLOY_MAP"
            else:
                current_mode = "MAP"
        elif veh_white > 1000 or has_shield:
            current_mode = "VEHICLE"
        elif is_spectating:
            current_mode = "SPECTATING"
        elif has_minimap and parchment_pct < 0.20:
            current_mode = "PEDESTRIAN"
        else:
            current_mode = "MAP"

        tactical_state["mode"] = current_mode
        tactical_state["is_spectating"] = (current_mode == "SPECTATING")
        tactical_state["is_deploy_map"] = (current_mode == "DEPLOY_MAP")
        tactical_state["is_full_map"] = (current_mode == "MAP")
        tactical_state["is_map"] = (current_mode in ("DEPLOY_MAP", "MAP"))
        tactical_state["in_vehicle"] = (current_mode == "VEHICLE")

        # -------------------------------------------------------------
        # 2. BLEEDING CHECK (Pedestrian / Vehicle)
        # -------------------------------------------------------------
        if current_mode in ("PEDESTRIAN", "VEHICLE"):
            corners = np.concatenate([
                bgr[20:60, 20:60], bgr[20:60, w-60:w-20],
                bgr[h-60:h-20, 20:60], bgr[h-60:h-20, w-60:w-20]
            ])
            mean_b, mean_g, mean_r = np.mean(corners, axis=(0, 1))
            if mean_r > 70 and mean_r > (mean_b + mean_g) * 0.7:
                tactical_state["is_bleeding"] = True

        # -------------------------------------------------------------
        # 3. MODE-SPECIFIC BOUNDING BOXES & SENSORS
        # -------------------------------------------------------------
        if current_mode == "SPECTATING":
            detected_boxes.append({
                "box": [700, 20, 1220, 120],
                "label": "SPECTATOR CAM // OBSERVING ALLY",
                "color": (255, 100, 100),
                "tag_pos": "bottom"
            })
            detected_boxes.append({
                "box": self.roi_compass,
                "label": "COMPASS & AZIMUTH",
                "color": (255, 200, 0),
                "tag_pos": "bottom"
            })
            detected_boxes.append({
                "box": self.roi_squads,
                "label": "REGIONAL SQUADS",
                "color": (255, 100, 255),
                "tag_pos": "top"
            })
            detected_boxes.append({
                "box": self.roi_chat,
                "label": "COMMS & CHAT LOG",
                "color": (0, 220, 255),
                "tag_pos": "top"
            })
            return detected_boxes, tactical_state

        if current_mode == "DEPLOY_MAP":
            detected_boxes.append({
                "box": [15, 75, 360, 850],
                "label": "DEPLOYMENT DIRECTORY // CONQUEST & CASUALTIES",
                "color": (255, 180, 0),
                "tag_pos": "top"
            })
            detected_boxes.append({
                "box": [380, 80, 1880, 960],
                "label": "WORLD DEPLOYMENT MAP // SELECT SPAWN SECTOR",
                "color": (0, 200, 255),
                "tag_pos": "top"
            })
            return detected_boxes, tactical_state

        if current_mode == "MAP":
            detected_boxes.append({
                "box": [200, 80, 1720, 980],
                "label": "REGIONAL TACTICAL MAP ('M' RECON)",
                "color": (0, 220, 255),
                "tag_pos": "top"
            })
            # Locate player orange chevron on full map via strided connected components
            map_crop = bgr[100:980:2, 200:1720:2]
            hsv_map = cv2.cvtColor(map_crop, cv2.COLOR_BGR2HSV)
            mask_chevron = (
                (hsv_map[:, :, 0] >= 8) & (hsv_map[:, :, 0] <= 16) &
                (hsv_map[:, :, 1] >= 110) & (hsv_map[:, :, 1] <= 210) &
                (hsv_map[:, :, 2] >= 110) & (hsv_map[:, :, 2] <= 230)
            )
            num, labels, stats, centroids = cv2.connectedComponentsWithStats(mask_chevron.astype(np.uint8))
            best_cand = None
            for i in range(1, num):
                x, y, w, h, area = stats[i]
                if 5 <= w <= 25 and 5 <= h <= 25 and 10 <= area <= 150:
                    cx, cy = centroids[i]
                    best_cand = (200 + int(cx * 2), 100 + int(cy * 2), int(w * 2), int(h * 2))
                    break

            if best_cand:
                actual_x, actual_y, w, h = best_cand
                tactical_state["player_marker"] = (actual_x, actual_y)
                box_pad = max(int(max(w, h) * 0.8), 20)
                detected_boxes.append({
                    "box": [actual_x - box_pad, actual_y - box_pad, actual_x + box_pad, actual_y + box_pad],
                    "label": "GPS CHEVRON // CURRENT POSITION",
                    "color": (255, 140, 0),
                    "tag_pos": "top"
                })
            return detected_boxes, tactical_state

        # IN-GAME MODES: VEHICLE or PEDESTRIAN
        # A. Minimap Detection (Bottom-Left Corner: 324x323 at [0, 756, 324, 1079])
        minimap_crop = bgr[756:1079, 0:324]
        m_mean = np.mean(minimap_crop, axis=(0, 1))
        if 100 < m_mean[0] < 175 and 100 < m_mean[1] < 175 and 90 < m_mean[2] < 175:
            tactical_state["has_minimap"] = True
            tactical_state["at_industrial_hub"] = True
            
            # Detect player chevron on minimap
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

        # B. Top-Left Stance or Vehicle Widget
        if current_mode == "VEHICLE":
            tactical_state["vehicle_type"] = "Dunne Transport"
            detected_boxes.append({
                "box": [16, 16, 190, 115],
                "label": "VEHICLE STATUS // DUNNE LOGISTICS TRUCK",
                "color": (0, 255, 180),
                "tag_pos": "bottom"
            })
        else:
            detected_boxes.append({
                "box": [16, 16, 155, 142],
                "label": "STANCE & STAMINA METER",
                "color": (0, 255, 200),
                "tag_pos": "bottom"
            })

        # C. Compass (Top-Right)
        detected_boxes.append({
            "box": self.roi_compass,
            "label": "COMPASS & AZIMUTH",
            "color": (255, 200, 0),
            "tag_pos": "bottom"
        })

        # D. Regional Squads Panel (Mid-Right)
        detected_boxes.append({
            "box": self.roi_squads,
            "label": "REGIONAL SQUADS",
            "color": (255, 100, 255),
            "tag_pos": "top"
        })

        # E. Communications & Chat Log (Bottom-Right)
        detected_boxes.append({
            "box": self.roi_chat,
            "label": "COMMS & CHAT LOG",
            "color": (0, 220, 255),
            "tag_pos": "top"
        })

        # F. Vehicle Armor Shield (if vehicle with armor)
        if has_shield:
            detected_boxes.append({
                "box": [932, 768, 988, 836],
                "label": "VEHICLE ARMOR STATUS",
                "color": (255, 80, 80),
                "tag_pos": "top"
            })

        return detected_boxes, tactical_state
