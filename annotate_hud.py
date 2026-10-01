import sys
from PIL import Image, ImageDraw, ImageFont

raw_path = "/home/user/Documents/foxhole-hud/current_screen_raw.png"
out_path = "/home/user/Documents/foxhole-hud/native_hud_bounding_boxes.png"

im = Image.open(raw_path).convert("RGBA")
overlay = Image.new("RGBA", im.size, (0, 0, 0, 0))
draw = ImageDraw.Draw(overlay)

try:
    font_label = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 11)
    font_desc = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 9)
    font_hdr = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 15)
    font_sub = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 11)
except Exception:
    font_label = ImageFont.load_default()
    font_desc = ImageFont.load_default()
    font_hdr = ImageFont.load_default()
    font_sub = ImageFont.load_default()

# Native HUD ROIs precisely measured from the screen
rois = [
    {
        "name": "ROI 1: VEHICLE PASSENGER & STAMINA",
        "desc": "Stance, seat role ('Passenger'), and sprint stamina meter",
        "box": [8, 14, 175, 130],
        "color": (0, 255, 200),
        "tag_pos": "bottom"
    },
    {
        "name": "ROI 2: COMPASS & WIND AZIMUTH",
        "desc": "Bearing dial (N/E/S/W), camera azimuth, and artillery wind vector",
        "box": [1770, 18, 1895, 142],
        "color": (255, 200, 0),
        "tag_pos": "bottom"
    },
    {
        "name": "ROI 3: REGIONAL SQUAD PANEL",
        "desc": "Regional / Global squad roster, operational groups, locked squads",
        "box": [1670, 308, 1902, 638],
        "color": (255, 100, 255),
        "tag_pos": "top"
    },
    {
        "name": "ROI 4: COMMUNICATIONS & CHAT LOG",
        "desc": "Tabs (All, Region, Logi, Intel), channel logs, active chatter",
        "box": [1365, 646, 1902, 932],
        "color": (0, 220, 255),
        "tag_pos": "top"
    },
    {
        "name": "ROI 5: SUBREGION LOCATION BANNER",
        "desc": "Dynamic subregion title: 'Fort Viper : Afric\\'s Approach' (Marban Hollow)",
        "box": [550, 664, 1370, 735],
        "color": (50, 255, 100),
        "tag_pos": "top"
    },
    {
        "name": "ROI 6: VEHICLE ARMOR / STATUS SHIELD",
        "desc": "Active vehicle armor integrity indicator",
        "box": [932, 768, 988, 836],
        "color": (255, 80, 80),
        "tag_pos": "bottom"
    },
    {
        "name": "ROI 7: ALLIED LOGISTICS VEHICLE & ESCORT",
        "desc": "Dunne Transport truck carrying player; Driver: Cartoffel (Col)",
        "box": [1020, 220, 1340, 560],
        "color": (255, 160, 40),
        "tag_pos": "top"
    }
]

for r in rois:
    bx0, by0, bx1, by1 = r["box"]
    rgb = r["color"]
    col_outline = (rgb[0], rgb[1], rgb[2], 255)
    col_fill = (rgb[0], rgb[1], rgb[2], 28)
    
    # 1. Translucent fill
    draw.rectangle([bx0, by0, bx1, by1], fill=col_fill)
    
    # 2. Outer border
    draw.rectangle([bx0, by0, bx1, by1], outline=col_outline, width=2)
    
    # 3. Tactical Corner brackets
    c_len = 14
    draw.line([(bx0, by0), (bx0 + c_len, by0)], fill=col_outline, width=3)
    draw.line([(bx0, by0), (bx0, by0 + c_len)], fill=col_outline, width=3)
    
    draw.line([(bx1, by0), (bx1 - c_len, by0)], fill=col_outline, width=3)
    draw.line([(bx1, by0), (bx1, by0 + c_len)], fill=col_outline, width=3)
    
    draw.line([(bx0, by1), (bx0 + c_len, by1)], fill=col_outline, width=3)
    draw.line([(bx0, by1), (bx0, by1 - c_len)], fill=col_outline, width=3)
    
    draw.line([(bx1, by1), (bx1 - c_len, by1)], fill=col_outline, width=3)
    draw.line([(bx1, by1), (bx1, by1 - c_len)], fill=col_outline, width=3)
    
    # 4. Badge / Tag label
    label_txt = r["name"]
    desc_txt = r["desc"]
    lw = max(font_label.getlength(label_txt), font_desc.getlength(desc_txt)) + 20
    lh = 34
    
    if r["tag_pos"] == "top":
        ty = by0 - lh - 4
        if ty < 55:  # avoid top header
            ty = by1 + 6
    else:
        ty = by1 + 6
        if ty + lh > 1070:
            ty = by0 - lh - 4
            
    tx = bx0
    if tx + lw > 1910:
        tx = 1910 - lw
    if tx < 10:
        tx = 10
        
    # Tag box
    draw.rounded_rectangle([tx, ty, tx + lw, ty + lh], radius=4, fill=(14, 18, 26, 235), outline=col_outline, width=1)
    draw.rounded_rectangle([tx + 1, ty + 1, tx + 4, ty + lh - 1], radius=2, fill=col_outline)
    draw.text((tx + 10, ty + 5), label_txt, font=font_label, fill=col_outline)
    draw.text((tx + 10, ty + 19), desc_txt, font=font_desc, fill=(220, 230, 240, 255))

# Top Banner
header_box = [15, 10, 1905, 52]
draw.rounded_rectangle(header_box, radius=5, fill=(12, 16, 24, 240), outline=(60, 140, 230, 255), width=2)
draw.text((960, 22), "NATIVE FOXHOLE HUD DETECTION & COMPUTER VISION CALIBRATION", font=font_hdr, fill=(245, 250, 255, 255), anchor="mm")
draw.text((960, 39), "Live Screen Capture (1920x1080) — Sector: Marban Hollow (Fort Viper : Afric's Approach) — Status: In Vehicle", font=font_sub, fill=(160, 200, 240, 255), anchor="mm")

# Composite and save
final_im = Image.alpha_composite(im, overlay)
final_im.convert("RGB").save(out_path, "PNG")
print("Saved annotated native HUD detection to", out_path)
