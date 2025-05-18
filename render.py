"""Code to render dynamic assets"""
from config import config
from utils import coalesce, mb_to_inHg

from math import pi, radians, sqrt
from io import BytesIO
import cairo
from airport_info import RunwayWindInfo, Airport
from metar_taf_parser.parser.parser import Metar
from metar_taf_parser.model.model import Wind

RENDERING_CONFIG = config["rendering"]
RW_CONFIG = RENDERING_CONFIG["runway"]
ADDITIONAL_INFO_CONFIG = RENDERING_CONFIG["additional_info"]
MINI_RW_CONFIG = ADDITIONAL_INFO_CONFIG["mini_runway"]

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

def _set_clearview_font(cr: cairo.Context):
    cr.select_font_face("Clearview", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL)

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
    _set_clearview_font(cr)
    cr.set_font_size(RW_CONFIG["numbers_font_size"])
    numbers_vertical_offset = RW_CONFIG["numbers_vertical_offset"]

    s = rw.le_ident
    voffset = (rwh / 2) - numbers_vertical_offset - (0 if background_mode else (threshold_vertical_offset + threshold_bars_height))
    x, y, text_width, text_height, dx, dy = cr.text_extents(s)
    cr.move_to(-(text_width / 2) - 0.004, voffset + (text_height / 2))
    cr.show_text(s)
    cr.stroke()

    s = rw.he_ident
    voffset = (rwh / 2) - numbers_vertical_offset - (0 if background_mode else (threshold_vertical_offset + threshold_bars_height))
    x, y, text_width, text_height, dx, dy = cr.text_extents(s)
    cr.move_to((text_width / 2) + 0.004, -voffset - (text_height / 2))
    cr.rotate(pi)
    cr.show_text(s)
    cr.stroke()

    cr.restore()

def _render_wind_compass(cr: cairo.Context, wind: Wind):
    r = RW_CONFIG["compass_radius"]

    # Wind pointer
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

    # Circle outline - currently disabled (alpha = 0)
    cr.save()
    cr.set_source_rgba(0, 0, 0, RW_CONFIG["compass_outline_alpha"])
    cr.set_line_width(RW_CONFIG["compass_majortick_line_width"])
    cr.translate(0.5, 0.5)
    cr.arc(0, 0, r, 0, 2 * pi)
    cr.close_path()
    cr.stroke()
    cr.restore()

    # Tick setup
    cr.save()
    cr.set_source_rgba(0, 0, 0, 1)
    cr.set_line_width(RW_CONFIG["compass_majortick_line_width"])
    _set_clearview_font(cr)
    cr.set_font_size(RW_CONFIG["compass_font_size"])
    
    # Rotate everything so north is facing up - note this virtually flips x & y axes
    cr.translate(0.5, 0.5)
    cr.rotate(-pi / 2)
    offset = int(360 / N_MAJOR_SEGMENTS)

    # Major ticks
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
        
        # Weird axes due to rotation
        x, y, text_width, text_height, dx, dy = cr.text_extents(s)

        # Draw white outline
        # TODO come up with a better way to distinguish numbers when it overlaps with arrow
        cr.save()
        cr.set_source_rgba(0.957, 0.957, 0.957, 1)
        cr.move_to(r - RW_CONFIG["compass_majortick_offsets"][1] - text_height - 0.01, -(text_width / 2) - 0.002)
        cr.rotate(pi / 2)
        cr.text_path(s)
        cr.stroke()
        cr.restore()

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
    # Minor ticks
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

    ws = coalesce(wind.speed, 1)
    gust = coalesce(wind.gust, ws)
    r = RW_CONFIG["compass_radius"] + RW_CONFIG["wind_gauge_radius_extension"]
    n_rectangles = N_MINOR_SEGMENTS // 2

    # Rotate so we start at north
    cr.rotate(-pi / 2 + (pi / n_rectangles))

    # Draw rectanges in circular pattern with appropriate colors
    for wsi in range(1, n_rectangles + 1):
        cm = WIND_GAUGE_ACTIVE_COLOR_MAP if wsi <= gust else WIND_GAUGE_INACTIVE_COLOR_MAP
        rgba = cm[wsi] if wsi in cm.keys() else (0, 0, 0, 1)
        cr.set_source_rgba(*rgba)
        _centered_rectangle(cr, r, 0, RW_CONFIG["wind_gauge_rectangle_height"], RW_CONFIG["wind_gauge_rectangle_width"])
        cr.fill()
        if ws < wsi <= gust:
            lw = RW_CONFIG["wind_gauge_gust_highlight_line_width"]
            cr.set_line_width(lw)
            cr.set_source_rgba(*RW_CONFIG["wind_gauge_gust_highlight_color"])
            _centered_rectangle(cr, r, 0, RW_CONFIG["wind_gauge_rectangle_height"] - lw, RW_CONFIG["wind_gauge_rectangle_width"] - lw)
            cr.stroke()

        cr.rotate(2 * pi / n_rectangles)
    cr.restore()

def _format_wind_str(min_wind, max_wind):
    return f"{abs(int(round(min_wind, 0)))}kt" if abs(min_wind - max_wind) <= 0.01 else f"{abs(int(round(min_wind, 0)))}-{abs(int(round(max_wind, 0)))}kt"

def _render_mini_runway_wind(cr: cairo.Context, rwi: RunwayWindInfo):
    """Render mini runway for crosswind additional info"""
    cr.save()
    cr.translate(0.5, 0.5)

    cr.set_line_width(0.002)
    cr.set_source_rgba(0, 0, 0, 1)

    # Draw runway as a centered trapezoid
    base_y = MINI_RW_CONFIG["base_y"]
    top_y = MINI_RW_CONFIG["top_y"]
    h = top_y - base_y
    base_width = MINI_RW_CONFIG["base_width"]
    top_width = MINI_RW_CONFIG["top_width"]
    cr.move_to( (base_width / 2), base_y)
    cr.line_to(-(base_width / 2), base_y)
    cr.line_to(-(top_width / 2), top_y)
    cr.line_to( (top_width / 2), top_y)
    cr.close_path()
    cr.fill()

    # Draw threshold bars using appropriate scaling
    cr.set_source_rgba(1, 1, 1, 1)
    threshold_n_bars = RW_CONFIG["threshold_n_bars"]
    threshold_base_width = MINI_RW_CONFIG["threshold_base_width"]
    threshold_height = MINI_RW_CONFIG["threshold_height"]

    # Width of the overall trapazoid
    top_of_threshold_total_width = base_width - ((threshold_height / h) * (top_width - base_width))
    top_of_threshold_bar_width = threshold_base_width - ((threshold_height / h) * (top_width - base_width))
    base_center_x = 1 / (2 * threshold_n_bars)
    for i in range(threshold_n_bars):
        center_x_pct = ((2 * i + 1) / (2 * threshold_n_bars))
        base_center_x = (base_width * center_x_pct) - (base_width / 2)
        top_of_threshold_center_x = (top_of_threshold_total_width * center_x_pct) - (top_of_threshold_total_width / 2)

        cr.move_to(base_center_x - (threshold_base_width / 2), base_y - 0.01)
        cr.line_to(base_center_x + (threshold_base_width / 2), base_y - 0.01)
        cr.line_to(top_of_threshold_center_x - (top_of_threshold_bar_width / 2), base_y - threshold_height)
        cr.line_to(top_of_threshold_center_x + (top_of_threshold_bar_width / 2), base_y - threshold_height)
        cr.close_path()
        cr.fill()

    _set_clearview_font(cr)
    cr.set_font_size(MINI_RW_CONFIG["numbers_font_size"])

    xws = rwi.runway.le_ident if rwi.favorable_dir == "le" else rwi.runway.he_ident
    x, y, text_width, text_height, dx, dy = cr.text_extents(xws)
    cr.move_to(-(text_width / 2) - 0.004, -0.3)
    cr.show_text(xws)
    cr.fill()

    # Headwind arrow
    wind_arrow_line_width = MINI_RW_CONFIG["wind_arrow_line_width"]
    wind_arrow_vertical_offset = MINI_RW_CONFIG["wind_arrow_vertical_offset"]
    wind_arrow_horizontal_offset = MINI_RW_CONFIG["wind_arrow_horizontal_offset"]

    wind_arrow_width = MINI_RW_CONFIG["wind_arrow_width"]
    wind_arrow_height = MINI_RW_CONFIG["wind_arrow_height"]

    cr.set_line_width(wind_arrow_line_width)
    cr.set_source_rgba(0, 0, 0, 1)
    headwind_arrow_vertical_offset = 0.06
    xws = (-1 if rwi.max_crosswind < 0 else 1)
    x_pos = xws * ((base_width / 2) + wind_arrow_horizontal_offset + 0.02)
    cr.move_to(x_pos, base_y - wind_arrow_height - wind_arrow_vertical_offset + headwind_arrow_vertical_offset)
    cr.line_to(x_pos, top_y + headwind_arrow_vertical_offset)
    cr.stroke()

    # Headwind arrowhead
    cr.move_to(x_pos, base_y - wind_arrow_vertical_offset + headwind_arrow_vertical_offset)
    cr.line_to(x_pos + (wind_arrow_width / 2), base_y - wind_arrow_height - wind_arrow_vertical_offset + headwind_arrow_vertical_offset)
    cr.line_to(x_pos - (wind_arrow_width / 2), base_y - wind_arrow_height - wind_arrow_vertical_offset + headwind_arrow_vertical_offset)
    cr.close_path()
    cr.fill()

    # Crosswind arrow
    aspect_ratio = ADDITIONAL_INFO_CONFIG["size"][0] / ADDITIONAL_INFO_CONFIG["size"][1]
    wind_arrow_line_width *= aspect_ratio
    wind_arrow_crosswind_line_length = MINI_RW_CONFIG["wind_arrow_crosswind_line_length"]
    wind_arrow_width *= aspect_ratio
    wind_arrow_height /= aspect_ratio

    cr.set_line_width(wind_arrow_line_width)
    x_pos = -xws * ((base_width / 2) + wind_arrow_horizontal_offset)
    x_offset = -xws * wind_arrow_crosswind_line_length
    cr.move_to(x_pos + -xws * wind_arrow_height, base_y - wind_arrow_vertical_offset - (wind_arrow_width / 2))
    cr.line_to(x_pos + x_offset, base_y - wind_arrow_vertical_offset - (wind_arrow_width / 2))
    cr.stroke()

    # Crosswind arrowhead
    cr.move_to(x_pos, base_y - wind_arrow_vertical_offset - (wind_arrow_width / 2))
    cr.line_to(x_pos + -xws * wind_arrow_height, base_y - wind_arrow_vertical_offset - (wind_arrow_width / 2) + xws * (wind_arrow_width / 2))
    cr.line_to(x_pos + -xws * wind_arrow_height, base_y - wind_arrow_vertical_offset - (wind_arrow_width / 2) - xws * (wind_arrow_width / 2))
    cr.close_path()
    cr.fill()

    # Headwind text
    text_horizontal_offset = MINI_RW_CONFIG["wind_text_horizontal_offset"]
    s = _format_wind_str(rwi.min_headwind, rwi.max_headwind)
    
    cr.set_source_rgba(0, 0, 0, 1)
    _set_clearview_font(cr)
    cr.set_font_size(MINI_RW_CONFIG["wind_text_font_size"])
    cr.set_line_width(0.0)
    cr.scale(1, aspect_ratio)

    x, y, text_width, text_height, dx, dy = cr.text_extents(s)
    cr.move_to(xws * ((base_width / 2) + text_horizontal_offset) - (text_width if xws == -1 else 0), -text_height)
    cr.text_path(s)
    cr.fill()

    # Crosswind text
    s = _format_wind_str(rwi.min_crosswind, rwi.max_crosswind)
    x, y, text_width, text_height, dx, dy = cr.text_extents(s)
    cr.move_to(-xws * ((base_width / 2) + text_horizontal_offset) - (text_width if xws == 1 else 0), -text_height)
    cr.text_path(s)
    cr.fill()

    # Overall wind text
    s = f"{rwi.wind.degrees}@{_format_wind_str(rwi.wind.speed, coalesce(rwi.wind.gust, rwi.wind.speed))}"
    cr.select_font_face("Clearview", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
    x, y, text_width, text_height, dx, dy = cr.text_extents(s)
    cr.move_to(-(text_width / 2), (text_height / 2) + 0.01)
    cr.text_path(s)
    cr.fill()

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

# TODO cache rendering functions by syncing this with the METAR caching
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
    w, h = ADDITIONAL_INFO_CONFIG["size"]
    aspect_ratio = w / h
    # TODO finish & clean up this component
    # TODO cleanup metar text in an html component

    output, surface, cr = _setup_canvas(w, h)

    backsplash_color = ADDITIONAL_INFO_CONFIG["backsplash_color"]
    # Flight category backsplash
    cr.set_line_width(0.0)
    cr.set_source_rgba(*ADDITIONAL_INFO_CONFIG["flight_category_colors"][airport.flight_category])
    flight_cat_backsplash_path = ADDITIONAL_INFO_CONFIG["flight_category_backsplash"]
    cr.move_to(*flight_cat_backsplash_path[0])
    cr.line_to(*flight_cat_backsplash_path[1])
    cr.line_to(*flight_cat_backsplash_path[2])
    cr.line_to(*flight_cat_backsplash_path[3])
    cr.line_to(*flight_cat_backsplash_path[4])
    cr.line_to(*flight_cat_backsplash_path[5])
    cr.close_path()
    cr.fill()

    # Visibility backsplash
    backsplash_rect_path = ADDITIONAL_INFO_CONFIG["visibility_backsplash"]["rectangle"]
    vxb_x, vxb_y, vxb_w, vxb_h = backsplash_rect_path[0][0], backsplash_rect_path[0][1], backsplash_rect_path[1][0] - backsplash_rect_path[0][0], backsplash_rect_path[2][1] - backsplash_rect_path[1][1]
    cr.set_source_rgba(*backsplash_color)
    cr.move_to(*backsplash_rect_path[0])
    cr.line_to(*backsplash_rect_path[1])
    cr.line_to(*backsplash_rect_path[2])
    cr.line_to(*backsplash_rect_path[3])
    cr.close_path()
    cr.fill()

    # Visibility chevron
    cr.set_source_rgba(*ADDITIONAL_INFO_CONFIG["flight_category_colors"][airport.visibility_flight_category])
    chevron_path = ADDITIONAL_INFO_CONFIG["visibility_backsplash"]["chevron"]
    cr.move_to(*chevron_path[0])
    cr.line_to(*chevron_path[1])
    cr.line_to(*chevron_path[2])
    cr.line_to(*chevron_path[3])
    cr.close_path()
    cr.fill()

    # Ceiling backsplash
    backsplash_vertical_offset = ADDITIONAL_INFO_CONFIG["backsplash_vertical_offset"]
    backsplash_rect_path = [[p[0], p[1] + backsplash_vertical_offset] for p in backsplash_rect_path]
    ceilb_x, ceilb_y, ceilb_w, ceilb_h = backsplash_rect_path[0][0], backsplash_rect_path[0][1], backsplash_rect_path[1][0] - backsplash_rect_path[0][0], backsplash_rect_path[2][1] - backsplash_rect_path[1][1]
    cr.set_source_rgba(*backsplash_color)
    cr.move_to(*backsplash_rect_path[0])
    cr.line_to(*backsplash_rect_path[1])
    cr.line_to(*backsplash_rect_path[2])
    cr.line_to(*backsplash_rect_path[3])
    cr.close_path()
    cr.fill()

    # Ceiling chevron
    chevron_path = [[p[0], p[1] + backsplash_vertical_offset] for p in chevron_path]
    cr.set_source_rgba(*ADDITIONAL_INFO_CONFIG["flight_category_colors"][airport.ceiling_flight_category])
    cr.move_to(*chevron_path[0])
    cr.line_to(*chevron_path[1])
    cr.line_to(*chevron_path[2])
    cr.line_to(*chevron_path[3])
    cr.close_path()
    cr.fill()

    # Temperature / dewpoint backsplash
    backsplash_rect_path = [[p[0], p[1] + backsplash_vertical_offset] for p in backsplash_rect_path]
    tempb_x, tempb_y, tempb_w, tempb_h = backsplash_rect_path[0][0], backsplash_rect_path[0][1], backsplash_rect_path[1][0] - backsplash_rect_path[0][0], backsplash_rect_path[2][1] - backsplash_rect_path[1][1]
    cr.set_source_rgba(*backsplash_color)
    cr.move_to(*backsplash_rect_path[0])
    cr.line_to(*backsplash_rect_path[1])
    cr.line_to(*backsplash_rect_path[2])
    cr.line_to(*backsplash_rect_path[3])
    cr.close_path()
    cr.fill()

    # Altimeter backsplash
    backsplash_rect_path = [[p[0], p[1] + backsplash_vertical_offset] for p in backsplash_rect_path]
    altb_x, altb_y, altb_w, altb_h = backsplash_rect_path[0][0], backsplash_rect_path[0][1], backsplash_rect_path[1][0] - backsplash_rect_path[0][0], backsplash_rect_path[2][1] - backsplash_rect_path[1][1]
    cr.move_to(*backsplash_rect_path[0])
    cr.line_to(*backsplash_rect_path[1])
    cr.line_to(*backsplash_rect_path[2])
    cr.line_to(*backsplash_rect_path[3])
    cr.close_path()
    cr.fill()

    # Render text
    cr.save()
    cr.scale(1, aspect_ratio)
    cr.set_line_width(0.003)

    # Flight category text
    s = airport.flight_category
    cr.set_source_rgba(1, 1, 1, 1)
    cr.select_font_face("Clearview", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
    cr.set_font_size(0.05)
    text_horizontal_margin = ADDITIONAL_INFO_CONFIG["text_horizontal_margin"]
    text_vertical_margin = ADDITIONAL_INFO_CONFIG["text_vertical_margin"]
    _x, _y, text_width, text_height, dx, dy = cr.text_extents(s)
    cr.move_to(text_horizontal_margin, text_height + text_vertical_margin)
    cr.text_path(s)
    cr.fill()

    # Visibility text
    s = airport.metar.visibility.distance
    cr.set_font_size(0.04)
    cr.set_source_rgba(0, 0, 0, 1)
    cr.select_font_face("Clearview", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
    _x, _y, text_width, text_height, dx, dy = cr.text_extents(s)
    cr.move_to(text_horizontal_margin, ((vxb_y + (vxb_h / 2)) / aspect_ratio) + (text_height / 2))
    cr.text_path(s)
    cr.fill()

    s = "Vis"
    cr.set_font_size(0.03)
    cr.set_source_rgba(0, 0, 0, 1)
    cr.select_font_face("Clearview", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL)
    _x, _y, text_width, text_height, dx, dy = cr.text_extents(s)
    cr.move_to(vxb_x + vxb_w - text_width - 0.06, ((vxb_y + (vxb_h / 2)) / aspect_ratio))
    cr.text_path(s)
    cr.fill()

    # Ceiling text
    s = f"{airport.cloud_ceiling}ft"
    cr.set_font_size(0.04)
    cr.set_source_rgba(0, 0, 0, 1)
    cr.select_font_face("Clearview", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
    _x, _y, text_width, text_height, dx, dy = cr.text_extents(s)
    cr.move_to(text_horizontal_margin, ((ceilb_y + (ceilb_h / 2)) / aspect_ratio) + (text_height / 2))
    cr.text_path(s)
    cr.fill()

    # Temperature / dewpoint text
    s = f"{airport.metar.temperature} / {airport.metar.dew_point}"
    cr.set_font_size(0.04)
    cr.set_source_rgba(0, 0, 0, 1)
    cr.select_font_face("Clearview", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
    _x, _y, text_width, text_height, dx, dy = cr.text_extents(s)
    cr.move_to(text_horizontal_margin, ((tempb_y + (tempb_h / 2)) / aspect_ratio) + (text_height / 2))
    cr.text_path(s)
    cr.fill()

    s = "˚C"
    cr.set_font_size(0.03)
    cr.set_source_rgba(0, 0, 0, 1)
    cr.select_font_face("Clearview", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL)
    _x, _y, text_width, text_height, dx, dy = cr.text_extents(s)
    cr.move_to(tempb_x + tempb_w - text_width - 0.04, ((tempb_y + (tempb_h / 2)) / aspect_ratio) + 0.01)
    cr.text_path(s)
    cr.fill()

    # Altimeter text
    s = f"{mb_to_inHg(airport.metar.altimeter):4.2f}\""
    cr.set_font_size(0.04)
    cr.set_source_rgba(0, 0, 0, 1)
    cr.select_font_face("Clearview", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
    _x, _y, text_width, text_height, dx, dy = cr.text_extents(s)
    cr.move_to(text_horizontal_margin, ((altb_y + (altb_h / 2)) / aspect_ratio) + (text_height / 2))
    cr.text_path(s)
    cr.fill()

    cr.restore()

    _render_mini_runway_wind(cr, airport.runway_wind_info[0])

    _cleanup_canvas(surface, output)

    return output

# TODO render cloud coverage
def render_metar_cloud_cover():
    w, h = 120, 480
    output, surface, cr = _setup_canvas(w, h, background_rgba=(0, 0, 1, 1))

    _cleanup_canvas(surface, output)

    return output