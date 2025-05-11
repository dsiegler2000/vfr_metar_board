"""Code to render dynamic assets"""
# %%
from config import config

from io import BytesIO
from PIL import Image, ImageDraw
from metar_taf_parser.parser.parser import Metar

CONFIG = config["rendering"]
METAR_CONFIG = CONFIG["metar"]

def draw_centered_rectangle(d, w, h, **kwargs):
    imw, imh = d.im.size
    print(imw, imh)
    print(w, h)
    # (360 / 2) - (320/2)
    print([int((imw / 2) - (w / 2)), int((imh / 2) - (h / 2)), 
                 int((imw / 2) + (w / 2)), int((imh / 2) + (h / 2))])
    d.rectangle([int((imw / 2) - (w / 2)), int((imh / 2) - (h / 2)), 
                 int((imw / 2) + (w / 2)), int((imh / 2) + (h / 2))], **kwargs)

def render_metar(metar: Metar):
    print(f"rendering metar: {metar.message}")

    w, h = METAR_CONFIG["size"]
    
    img = Image.new("RGBA", (w, h), color=(0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    
    # img1.rectangle(shape, fill ="#ffff33", outline ="red")
    rww, rwh = METAR_CONFIG["rw_size"]
    draw_centered_rectangle(d, rww, rwh, fill="green")

    # Save to buffer
    output = BytesIO()
    img.save(output, "png")
    output.seek(0)
    return output
# %%
