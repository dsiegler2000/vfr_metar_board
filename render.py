"""Code to render dynamic assets"""
from config import config
from utils import coalesce

from math import pi, radians, sqrt, sin, cos
from io import BytesIO
import cairo
from airport_info import RunwayWindInfo, Airport
from metar_taf_parser.parser.parser import Metar
from metar_taf_parser.model.model import Wind

RENDERING_CONFIG = config["rendering"]
RW_CONFIG = RENDERING_CONFIG["runway"]

N_MAJOR_SEGMENTS = 12
N_MINOR_SEGMENTS = 72

# Wind gauge color maps for active (wind is at least this strong) & inactive states
WIND_GAUGE_ACTIVE_COLOR_MAP = dict()
WIND_GAUGE_INACTIVE_COLOR_MAP = dict()
for wsi in range(1, (N_MINOR_SEGMENTS // 2) + 1):
    for c in RW_CONFIG["wind_gauge_active_color_bands"][::-1]:
        if wsi <= c[0]:
            WIND_GAUGE_ACTIVE_COLOR_MAP[wsi] = c[1:]
for wsi in range(1, (N_MINOR_SEGMENTS // 2) + 1):
    for c in RW_CONFIG["wind_gauge_inactive_color_bands"][::-1]:
        if wsi <= c[0]:
            WIND_GAUGE_INACTIVE_COLOR_MAP[wsi] = c[1:]

def _centered_rectangle(cr: cairo.Context, x_center, y_center, width, height):
    cr.rectangle(x_center - width / 2, y_center - height / 2, width, height)

def _render_runway(cr: cairo.Context, rwi: RunwayWindInfo, background_mode: bool=False):
    cr.save()

    rw = rwi.runway
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

    s = rw.le_ident
    voffset = (rwh / 2) - numbers_vertical_offset - (0 if background_mode else (threshold_vertical_offset + threshold_bars_height))
    x, y, text_width, text_height, dx, dy = cr.text_extents(s)
    cr.move_to(-(text_width / 2), voffset + (text_height / 2))
    cr.show_text(s)
    cr.stroke()

    s = rw.he_ident
    voffset = (rwh / 2) - numbers_vertical_offset - (0 if background_mode else (threshold_vertical_offset + threshold_bars_height))
    x, y, text_width, text_height, dx, dy = cr.text_extents(s)
    cr.move_to((text_width / 2), -voffset - (text_height / 2))
    cr.rotate(pi)
    cr.show_text(s)
    cr.stroke()

    cr.restore()

def _render_wind_compass(cr: cairo.Context, wind: Wind):
    # Wind pointer
    r = RW_CONFIG["compass_radius"]
    if wind.degrees is not None:
        w, h = RW_CONFIG["wind_arrow_width"], RW_CONFIG["wind_arrow_height"]
        ws = min(coalesce(wind.gust, wind.speed), 45)
        scaled_w, scaled_h = sqrt(5 * ws) * w, ws * h

        cr.save()
        cr.set_line_width(0.01)
        cr.set_source_rgba(0, 0, 0, 1)

        # Wind line
        cr.translate(0.5, 0.5)
        cr.rotate((-pi / 2) + radians(wind.degrees))
        cr.move_to(r, 0)
        cr.line_to(-r + scaled_h, 0)
        cr.stroke()

        # Arrowhead
        cr.move_to(r - scaled_h, 0)
        cr.line_to(r,  scaled_w)
        cr.line_to(r, -scaled_w)
        cr.close_path()
        cr.fill()

        cr.move_to(-r, 0)
        cr.line_to(-r + scaled_h,  scaled_w)
        cr.line_to(-r + scaled_h, -scaled_w)
        cr.close_path()
        cr.fill()

        cr.stroke()
        cr.restore()

    cr.save()
    cr.set_source_rgba(0, 0, 0, RW_CONFIG["compass_outline_alpha"])
    cr.set_line_width(RW_CONFIG["compass_majortick_line_width"])
    cr.translate(0.5, 0.5)
    cr.arc(0, 0, r, 0, 2 * pi)
    cr.close_path()
    cr.stroke()
    cr.restore()

    cr.save()
    cr.set_source_rgba(0, 0, 0, 1)
    cr.set_line_width(RW_CONFIG["compass_majortick_line_width"])
    cr.select_font_face("Clearview", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL)
    cr.set_font_size(RW_CONFIG["compass_font_size"])
    
    # Rotate everything so north is facing up - note this virtually flips x & y axes
    cr.translate(0.5, 0.5)
    cr.rotate(-pi / 2)
    offset = int(360 / N_MAJOR_SEGMENTS)
    for i in range(N_MAJOR_SEGMENTS):
        hdg = i * offset
        if hdg == 0:
            s = "N"
        elif hdg == 90:
            s = "E"
        elif hdg == 180:
            s = "S"
        elif hdg == 270:
            s = "W"
        else:
            s = str(int(hdg / 10))
        # Draw major tick
        cr.move_to(r + RW_CONFIG["compass_majortick_offsets"][0] + (RW_CONFIG["compass_northtick_extension"] if s == "N" else 0), 0)
        cr.line_to(r - RW_CONFIG["compass_majortick_offsets"][1], 0)
        cr.stroke()
        
        x, y, text_width, text_height, dx, dy = cr.text_extents(s)
        # Weird axes due to rotation

        # Draw white outline - currently disabled
        # TODO come up with a better way to distinguish numbers when it overlaps with arrow
        # cr.save()
        # cr.set_source_rgba(0.957, 0.957, 0.957, 1)
        # cr.move_to(r - RW_CONFIG["compass_majortick_offsets"][1] - text_height - 0.01, -(text_width / 2) - 0.002)
        # cr.rotate(pi / 2)
        # cr.text_path(s)
        # cr.stroke()
        # cr.restore()

        cr.move_to(r - RW_CONFIG["compass_majortick_offsets"][1] - text_height - 0.01, -(text_width / 2) - 0.002)
        cr.save()
        cr.rotate(pi / 2)
        cr.show_text(s)
        cr.stroke()
        cr.restore()

        # Rotate around circle
        cr.rotate(2 * pi / N_MAJOR_SEGMENTS)
    cr.restore()

    cr.save()
    cr.translate(0.5, 0.5)
    cr.rotate(-pi / 2)
    cr.set_line_width(RW_CONFIG["compass_minortick_line_width"])
    cr.set_source_rgba(0, 0, 0, RW_CONFIG["compass_minortick_alpha"])
    for i in range(N_MINOR_SEGMENTS):
        # Right side of circle
        cr.move_to(r + RW_CONFIG["compass_minortick_offsets"][0], 0)
        cr.line_to(r - RW_CONFIG["compass_minortick_offsets"][1], 0)
        cr.stroke()
        cr.rotate(2 * pi / N_MINOR_SEGMENTS)
    cr.restore()

def _render_wind_gauge(cr: cairo.Context, wind: Wind):
    cr.save()
    cr.set_source_rgba(1, 0, 0, 1)
    cr.translate(0.5, 0.5)

    ws = coalesce(wind.gust, wind.speed, 1)
    r = RW_CONFIG["compass_radius"] + RW_CONFIG["wind_gauge_radius_extension"]
    n_rectangles = N_MINOR_SEGMENTS // 2

    # Rotate so we start at north
    cr.rotate(-pi / 2 + (pi / n_rectangles))

    # Draw rectanges in circular pattern with appropriate colors
    for wsi in range(1, n_rectangles + 1):
        cm = WIND_GAUGE_ACTIVE_COLOR_MAP if wsi <= ws else WIND_GAUGE_INACTIVE_COLOR_MAP
        rgba = cm[wsi] if wsi in cm.keys() else (0, 0, 0, 1)
        cr.set_source_rgba(*rgba)
        _centered_rectangle(cr, r, 0, RW_CONFIG["wind_gauge_rectangle_height"], RW_CONFIG["wind_gauge_rectangle_width"])
        cr.fill()
        cr.rotate(2 * pi / n_rectangles)
    cr.restore()

def _setup_canvas(w, h, background_rgba=(0, 0, 0, 0)):
    output = BytesIO()
    surface = cairo.SVGSurface(output, w, h)
    cr = cairo.Context(surface)
    cr.set_antialias(cairo.ANTIALIAS_NONE)
    cr.scale(w, h)

    # Background
    cr.set_source_rgba(*background_rgba)
    cr.rectangle(0, 0, 1, 1)
    cr.fill()

    return output, surface, cr

def _cleanup_canvas(surface, output):
    surface.flush()
    surface.finish()

    output.flush()
    output.seek(0)

    return output

def render_metar_wind(airport: Airport):
    w, h = RW_CONFIG["size"]
    output, surface, cr = _setup_canvas(w, h)

    metar = airport.metar
    _render_wind_gauge(cr, metar.wind)
    _render_wind_compass(cr, metar.wind)

    rwis = airport.runway_wind_info
    for i, rwi in enumerate(rwis):
        # Highlight favored runway
        _render_runway(cr, rwi, background_mode=i > 0)

    _cleanup_canvas(surface, output)

    return output

def render_metar_additional_info(airport: Airport):
    w, h = 360, 120
    # TODO make component for VFR/IFR status, XW info, & altimeter setting, temp, dewpoint, etc - like metar taf display mode
    output, surface, cr = _setup_canvas(w, h, background_rgba=(1, 0, 0, 1))

    fr_category = airport.flight_category

    _cleanup_canvas(surface, output)

    return output