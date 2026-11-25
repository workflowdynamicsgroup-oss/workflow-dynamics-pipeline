"""Shot 62a: both public pricing pages side by side on a 1920x1080 light card, GoHighLevel on the left.
Usage: python3 render/compose_62a.py GHL.png SYSTEME.png OUT.png
"""
import sys
from PIL import Image
a, b = Image.open(sys.argv[1]).convert("RGB"), Image.open(sys.argv[2]).convert("RGB")
W, H, GAP = 1920, 1080, 40
box_w, box_h = (W - 3 * GAP) // 2, H - 2 * GAP
canvas = Image.new("RGB", (W, H), (0xF4, 0xF7, 0xFB))
for n, im in enumerate((a, b)):
    s = min(box_w / im.width, box_h / im.height)
    r = im.resize((int(im.width * s), int(im.height * s)), Image.LANCZOS)
    canvas.paste(r, (GAP + n * (box_w + GAP) + (box_w - r.width) // 2, (H - r.height) // 2))
canvas.save(sys.argv[3]); print("COMPOSE_62A_OK", canvas.size)
