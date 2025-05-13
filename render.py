"""Code to render dynamic assets"""
from config import config

from math import pi, radians, sin, cos
from io import BytesIO
import cairo

RENDERING_CONFIG = config["rendering"]
RW_CONFIG = RENDERING_CONFIG["runway"]

def _centered_rectangle(cr, x_center, y_center, width, height):
    cr.rectangle(x_center - width / 2, y_center - height / 2, width, height)

def _centered_text(cr, x_center, y_center, s, theta=0):
    x, y, text_width, text_height, dx, dy = cr.text_extents(s)
    cr.save()
    if s == "N":
        print(x_center, text_width)
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
    cr.stroke()
    
    cr.restore()

def _render_wind_compass(cr, wind):
    cr.save()
    cr.set_source_rgba(0, 0, 0, RW_CONFIG["compass_outline_alpha"])
    cr.set_line_width(RW_CONFIG["compass_majortick_line_width"])
    cr.translate(0.5, 0.5)
    r = RW_CONFIG["compass_radius"]
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
    n_major_segments = 12
    offset = int(360 / n_major_segments)
    for i in range(n_major_segments):
        # Draw major tick
        cr.move_to(r + RW_CONFIG["compass_majortick_offsets"][0], 0)
        cr.line_to(r - RW_CONFIG["compass_majortick_offsets"][1], 0)
        cr.stroke()

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
        
        x, y, text_width, text_height, dx, dy = cr.text_extents(s)
        # Weird axes due to rotation
        cr.move_to(r - RW_CONFIG["compass_majortick_offsets"][1] - text_height - 0.01, -(text_width / 2) - 0.002)
        cr.save()
        cr.rotate(pi / 2)
        cr.show_text(s)
        cr.stroke()
        cr.restore()

        # Rotate around circle
        cr.rotate(2 * pi / n_major_segments)
    cr.restore()

    cr.save()
    cr.translate(0.5, 0.5)
    cr.rotate(-pi / 2)
    n_minor_segments = 72
    cr.set_line_width(RW_CONFIG["compass_minortick_line_width"])
    cr.set_source_rgba(0, 0, 0, RW_CONFIG["compass_minortick_alpha"])
    for i in range(n_minor_segments):
        # Right side of circle
        cr.move_to(r + RW_CONFIG["compass_minortick_offsets"][0], 0)
        cr.line_to(r - RW_CONFIG["compass_minortick_offsets"][1], 0)
        cr.stroke()
        cr.rotate(2 * pi / n_minor_segments)
    cr.restore()

    # Draw wind info - color indicates strength
    if wind.degrees is not None:
        print(wind)
        cr.save()
        cr.set_line_width(0.01)
        cr.set_source_rgba(0, 1, 0, 1)

        cr.translate(0.5, 0.5)
        cr.rotate((-pi / 2) + radians(wind.degrees))
        cr.move_to(r, 0)
        cr.line_to(-r, 0)
        cr.stroke()

        # Arrowhead
        cr.move_to(r - 0.05, 0)
        cr.line_to(r, 0.02)
        cr.line_to(r, -0.02)
        cr.close_path()
        cr.fill()

        cr.move_to(-r, 0)
        cr.line_to(-r + 0.05, 0.02)
        cr.line_to(-r + 0.05, -0.02)
        cr.close_path()
        cr.fill()

        cr.stroke()
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

    # TODO color wind compass arrow correctly
    _render_wind_compass(cr, metar.wind)

    rwis = airport.compute_rw_wind(metar, unique_rws_only=True)
    for i, rwi in enumerate(rwis):
        # Highlight favored runway
        _render_runway(cr, rwi.runway, background_mode=i > 0)

    # TODO add wind strength info

    surface.flush()
    surface.finish()

    output.flush()
    output.seek(0)

    return output