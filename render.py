"""Code to render dynamic assets"""
from config import config
from airport_info import Airport, Runway
from metar_taf_parser.parser.parser import Metar

from math import pi, radians
from io import BytesIO
import cairo

RENDERING_CONFIG = config["rendering"]
RW_CONFIG = RENDERING_CONFIG["runway"]

def _centered_rectangle(cr, x_center, y_center, width, height):
    cr.rectangle(x_center - width / 2, y_center - height / 2, width, height)

def _centered_text(cr, x_center, y_center, s, theta=0):
    x, y, text_width, text_height, dx, dy = cr.text_extents(s)
    cr.save()
    cr.move_to(x_center - (text_width / 2), y_center + (text_height / 2))
    cr.rotate(theta)
    cr.show_text(s)
    cr.restore()

def _render_runway(cr: cairo.Context, rw, background_mode=False):
    cr.save()

    alpha = RW_CONFIG["background_rw_alpha"] if background_mode else 1

    # Rotate & offset so drawing is relative to 0, 0
    cr.translate(0.5, 0.5)
    t = radians(rw.le_heading_degT)
    cr.rotate(t)

    # Runway base
    cr.set_source_rgba(0, 0, 0, alpha)
    rww, rwh = RW_CONFIG["rw_size"]
    _centered_rectangle(cr, 0, 0, rww, rwh)
    cr.fill()

    # Threshold markings
    threshold_n_bars = RW_CONFIG["threshold_n_bars"]
    threshold_bars_width, threshold_bars_height = RW_CONFIG["threshold_bars_width"], RW_CONFIG["threshold_bars_height"]
    threshold_vertical_offset = RW_CONFIG["threshold_vertical_offset"]
    threshold_spacing = rww / (threshold_n_bars + 1)
    if not background_mode:
        cr.set_source_rgba(1, 1, 1, alpha)
        voffset = (rwh / 2) - threshold_vertical_offset - (threshold_bars_height / 2)
        for i in range(threshold_n_bars):
            _centered_rectangle(cr, -(rww / 2) + ((i + 1) * threshold_spacing),  voffset, threshold_bars_width, threshold_bars_height)
            _centered_rectangle(cr, -(rww / 2) + ((i + 1) * threshold_spacing), -voffset, threshold_bars_width, threshold_bars_height)
        cr.fill()

    # Runway numbers
    cr.set_source_rgba(1, 1, 1, alpha)
    cr.select_font_face("Clearview", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL)
    cr.set_font_size(RW_CONFIG["numbers_font_size"])
    numbers_vertical_offset = RW_CONFIG["numbers_vertical_offset"]
    voffset = (rwh / 2) - numbers_vertical_offset - (0 if background_mode else (threshold_vertical_offset + threshold_bars_height))
    _centered_text(cr, 0,  voffset, rw.le_ident)
    _centered_text(cr, 0, -voffset, rw.he_ident)
    
    cr.restore()

def render_metar_wind(metar, airport):
    w, h = RW_CONFIG["size"]

    output = BytesIO()
    surface = cairo.SVGSurface(output, w, h)
    cr = cairo.Context(surface)
    cr.set_antialias(cairo.ANTIALIAS_NONE)
    cr.scale(w, h)

    # Background
    cr.set_source_rgba(0, 0, 0, 0)
    cr.rectangle(0, 0, 1, 1)
    cr.fill()

    for rw in airport.unique_runways:
        _render_runway(cr, rw, background_mode=rw.le_ident != "10L")

    # TODO add compass rose & wind strength indication

    surface.flush()
    surface.finish()

    output.flush()
    output.seek(0)

    return output