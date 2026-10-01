import os
from PIL import Image, ImageDraw, ImageFont

input_path = "/home/user/.gemini/antigravity-cli/brain/bd156143-50b1-4653-a8d3-eeedb8ed140d/.user_uploaded/uploaded_media_1790875325128.png"
output_path = "/home/user/Documents/foxhole/salt_march_watchtower_priorities.png"

orig = Image.open(input_path).convert("RGBA")
w, h = orig.size  # 646, 768

footer_h = 136
canvas = Image.new("RGBA", (w, h + footer_h), (18, 22, 28, 255))
canvas.paste(orig, (0, 0))

draw = ImageDraw.Draw(canvas)

try:
    f_title = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 11)
    f_desc = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 9)
    f_badge = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 11)
    f_hdr = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 13)
    f_sub = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 10)
    f_pill = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 9)
except Exception:
    f_title = ImageFont.load_default()
    f_desc = ImageFont.load_default()
    f_badge = ImageFont.load_default()
    f_hdr = ImageFont.load_default()
    f_sub = ImageFont.load_default()
    f_pill = ImageFont.load_default()

WT_RADIUS = 88

priorities = [
    {
        "pos": (330, 665),
        "num": 1,
        "name": "BRIDGEHEAD CHOKE",
        "tag_pos": (120, 680),
        "target": (330, 665),
        "title": "P1: RIVER BRIDGEHEAD (CRITICAL)",
        "cost": "60 Bmats",
        "threat": "Main Colonial assault route from Sunken Coup / Spine.",
        "action": "Build at north bridgehead. Essential for early alert on river crossings.",
        "color": (255, 65, 65),
        "fill": (255, 65, 65, 38),
        "border": (255, 75, 75, 230)
    },
    {
        "pos": (270, 520),
        "num": 2,
        "name": "STEPPES / MARSH FLANK",
        "tag_pos": (45, 470),
        "target": (270, 520),
        "title": "P2: STEPPES / MARSH BLIND SPOT",
        "cost": "60 Bmats",
        "threat": "Vast open frozen ground west of Salt March.",
        "action": "Plugs gap between west road and bridge road; stops sneaky infantry.",
        "color": (255, 175, 25),
        "fill": (255, 175, 25, 38),
        "border": (255, 175, 25, 220)
    },
    {
        "pos": (445, 670),
        "num": 3,
        "name": "SOUTH RIVER ROAD",
        "tag_pos": (475, 705),
        "target": (445, 670),
        "title": "P3: SOUTH RIVERBANK / EAST ROAD",
        "cost": "60 Bmats",
        "threat": "Southern river curve and rear access road.",
        "action": "Prevents southern shoreline bypasses and covers rear logi loop.",
        "color": (40, 215, 110),
        "fill": (40, 215, 110, 38),
        "border": (40, 215, 110, 220)
    },
    {
        "pos": (585, 560),
        "num": 4,
        "name": "EAST COAST GUARD",
        "tag_pos": (470, 480),
        "target": (585, 560),
        "title": "P4: EAST COAST / BORDER CUTOFF",
        "cost": "60 Bmats",
        "threat": "Deep east road & border huggers.",
        "action": "Detects waterborne landings and wide border partisans.",
        "color": (60, 175, 255),
        "fill": (60, 175, 255, 38),
        "border": (60, 175, 255, 210)
    }
]

# 1. Radar circles
for p in priorities:
    x, y = p["pos"]
    r = WT_RADIUS
    draw.ellipse([x - r, y - r, x + r, y + r], fill=p["fill"], outline=p["border"], width=2)

# 2. Pill labels and pins
for p in priorities:
    tx, ty = p["target"]
    px, py = p["tag_pos"]
    pw = 145
    
    # Leader line
    draw.line([(px + pw // 2, py + 10), (tx, ty)], fill=p["border"], width=2)
    
    # Pill box
    draw.rounded_rectangle([px, py, px + pw, py + 20], radius=4, fill=(12, 16, 24, 230), outline=p["color"], width=1)
    draw.rounded_rectangle([px + 2, py + 2, px + 18, py + 18], radius=3, fill=p["color"])
    draw.text((px + 10, py + 10), str(p["num"]), font=f_badge, fill=(0, 0, 0, 255), anchor="mm")
    draw.text((px + 23, py + 5), p["name"], font=f_pill, fill=(245, 245, 250, 255))
    
    # Target pin
    draw.ellipse([tx - 11, ty - 11, tx + 11, ty + 11], fill=(10, 15, 20, 240), outline=(255, 255, 255, 255), width=2)
    draw.ellipse([tx - 8, ty - 8, tx + 8, ty + 8], fill=p["color"])
    draw.text((tx, ty), str(p["num"]), font=f_badge, fill=(0, 0, 0, 255), anchor="mm")

# 3. Top Header
draw.rectangle([8, 8, w - 8, 42], fill=(14, 20, 30, 235), outline=(70, 140, 220, 255), width=1)
draw.text((w // 2, 18), "SALT MARCH DEFENSE GRID — WATCHTOWER BUILD ORDER", font=f_hdr, fill=(240, 245, 255, 255), anchor="mm")
draw.text((w // 2, 33), "Priority Sequence (Day 1 / Hour 1) — 60 Bmats per Watchtower — 80m Radar Coverage", font=f_sub, fill=(170, 200, 230, 255), anchor="mm")

# 4. Footer cards
deck_y = h + 4
card_w = (w - 24) // 2
card_h = 58

for i, p in enumerate(priorities):
    row = i // 2
    col = i % 2
    cx = 8 + col * (card_w + 8)
    cy = deck_y + row * (card_h + 6)
    
    draw.rounded_rectangle([cx, cy, cx + card_w, cy + card_h], radius=4, fill=(22, 28, 38, 255), outline=p["color"], width=1)
    draw.rounded_rectangle([cx, cy, cx + 5, cy + card_h], radius=2, fill=p["color"])
    draw.text((cx + 12, cy + 6), p["title"], font=f_title, fill=p["color"])
    draw.text((cx + card_w - 8, cy + 6), p["cost"], font=f_title, fill=(200, 220, 240, 255), anchor="ra")
    draw.text((cx + 12, cy + 22), p["threat"], font=f_desc, fill=(220, 225, 230, 255))
    draw.text((cx + 12, cy + 38), p["action"], font=f_desc, fill=(160, 180, 200, 255))

canvas.convert("RGB").save(output_path, "PNG")
print("Clean map rendered.")
