"""
ICAO codes will be default respected, with fallback to FAA LID
"""

import json 
import os
import httpx
from config import config
from dataclasses import dataclass
import re
from math import radians, sin, cos
from typing_extensions import Literal
import time

from utils import coalesce_int_from_float, coalesce_float, coalesce
from metar_taf_parser.model.model import Wind, Metar
from metar_taf_parser.model.enum import CloudQuantity
from aviation_weather import fetch_latest_metar

# Formatted as ceiling, (OR) viz, rules
FLIGHT_RULES_REQUIREMENTS = [
    (500, 1, "LIFR"),
    (1000, 3, "IFR"),
    (3000, 5, "MVFR"),
    (100_000, 100, "VFR"),
]

@dataclass
class Runway:
    length_ft: int
    width_ft: int
    surface: str
    lighted: bool
    closed: bool
    le_ident: str
    le_elevation_ft: int
    le_heading_degT: int
    le_displaced_threshold_ft: int
    he_ident: str
    he_elevation_ft: int
    he_heading_degT: int
    he_displaced_threshold_ft: int

    _dedupped_ident = None
    def get_dedupped_ident(self):
        if self._dedupped_ident is None:
            self._dedupped_ident = re.sub(r"(L|R|C)", "", self.le_ident)
        return self._dedupped_ident
    dedupped_ident = property(get_dedupped_ident)

@dataclass
class Frequency:
    airport_ident: str
    type: str
    description: str
    frequency_mhz: str

class RunwayWindInfo:
    runway: Runway
    wind: Wind

    favorable_dir: Literal["le", "he"]
    # le will be preferred
    is_preferred_rw_info: Literal["le", "he", "no", "unk", None]

    # True iff wind is gusting, VRB, or has variation
    variation: bool

    # Positive values indicate headwind & RIGHT crosswinds, & if no gust then both values will be equal
    min_headwind: float
    max_headwind: float
    min_crosswind: float
    max_crosswind: float

    def __init__(self, runway: Runway, wind: Wind, is_preferred_rw_info: Literal["le", "he", "no", "unk"]="unk", crosswind_map=None):
        if crosswind_map:
            raise ValueError("crosswind_map is not yet supported!")
        self.runway = runway
        self.wind = wind
        self.is_preferred_rw_info = is_preferred_rw_info


        if wind.direction == "VRB":
            self.variation = True
            self.min_headwind = self.wind.speed
            self.min_crosswind = self.wind.speed

            self.max_headwind = coalesce(self.wind.gust, self.wind.speed)
            self.max_crosswind = coalesce(self.wind.gust, self.wind.speed)
            self.favorable_dir = "calm"
        else:
            # Construct all possible wind directions & strengths
            if wind.gust is None and wind.min_variation is None:
                winds = [(wind.degrees, wind.speed)]
            elif wind.gust is None and wind.min_variation is not None:
                self.variation = True
                winds = [
                    (wind.degrees, wind.speed),
                    (wind.min_variation, wind.speed),
                    (wind.max_variation, wind.speed)
                ]
            elif wind.gust is not None and wind.min_variation is None:
                self.variation = True
                winds = [
                    (wind.degrees, wind.speed),
                    (wind.degrees, wind.gust)
                ]
            else:  # Both gust & variation
                self.variation = True
                winds = [
                    (wind.degrees, wind.speed),
                    (wind.min_variation, wind.speed),
                    (wind.max_variation, wind.speed),
                    (wind.degrees, wind.gust),
                    (wind.min_variation, wind.gust),
                    (wind.max_variation, wind.gust)
                ]

            computed_winds = []
            for w in winds:
                for end in ("le", "he"):
                    info = self._compute_wind_info(w[0], w[1], end)
                    computed_winds.append((info[0], info[1], end))
            # Sort by headwind
            computed_winds = sorted(computed_winds, key=lambda w: w[1], reverse=True)
            self.favorable_dir = computed_winds[0][2]
            self.min_crosswind = min([w[0] for w in computed_winds if w[2] == self.favorable_dir])
            self.max_crosswind = max([w[0] for w in computed_winds if w[2] == self.favorable_dir])
            self.min_headwind = min([w[1] for w in computed_winds if w[2] == self.favorable_dir])
            self.max_headwind = max([w[1] for w in computed_winds if w[2] == self.favorable_dir])

    def _compute_wind_info(self, dir, strength, runway_end):
        """Returns crosswind, headwind"""
        offset_deg = (self.runway.le_heading_degT if runway_end == "le" else self.runway.he_heading_degT) - dir
        offset = radians(offset_deg)
        return strength * sin(offset), strength * cos(offset)

@dataclass
class Airport:
    """
    Airport info & helper functions constructed from raw data. 
    Includes METAR info & additional info (cloud ceiling, flight category, etc). 
    """
    def __init__(self, ident: str, icao_code: str, iata_code: str, local_code: str, 
                       lat: float, long: float, elevation_ft: int, 
                       iso_country: str, runways: list[Runway], frequencies: list,
                       fast_compute=False):
        # Airport info
        self.ident = ident
        self.icao_code = icao_code
        self.iata_code = iata_code
        self.local_code = local_code
        self.lat = lat
        self.long = long
        self.elevation_ft = elevation_ft
        self.iso_country = iso_country
        # Filter out helipads, sometimes listed as "H1"
        self.runways = [r for r in runways if not (r.le_ident.lower().startswith("H") or r.he_ident.lower().startswith("H") or r.length_ft <= 200)]
        self.frequencies = frequencies

        # Cached unique runways
        self._unique_runways = None

        # Whether fast compute mode is enabled
        # TODO finish this code out -- 
        #  create df of weather conditions
        #  generate monthly averages by hour to store for each year
        #  then plot that shit (ok seperate)
        if fast_compute:
            self._crosswind_map = None 

            rw_info_full = []
            for rw in self.runways:
                for i in ["le", "he"]:
                    rw_info_full.append({
                        "length_ft": rw.length_ft,
                        "width_ft": rw.width_ft,
                        "lighted": rw.lighted,
                        "closed": rw.closed,
                        "ident": rw.le_ident if i == "le" else rw.he_ident,
                        "heading_true": rw[f"{i}_heading_true"],
                        "displaced_threshold_ft": rw[f"{i}_displaced_threshold_ft"],
                        "est_lda_ft": rw["est_lda_ft"],
                        "surface": rw["surface"]
                    })
            rw_df = pd.DataFrame(rw_info_full)


        else:
            self._crosswind_map = None

        # Cached METAR info
        self._last_metar_fetch_time = None
        self._metar = None
        self._cloud_ceiling = None
        self._runway_wind_info = None
        self._flight_category = "UNK"
        self._vx_flight_category = "UNK"
        self._ceiling_flight_category = "UNK"
        self._fetch_current_metar()

    def get_unique_runways(self):
        """Returns unique runways, excluding L/R/C duplicates"""
        if self._unique_runways is None:
            self._unique_runways = []
            unique_ident_already_added = set()
            for rw in self.runways:
                if rw.dedupped_ident not in unique_ident_already_added:
                    unique_ident_already_added.add(rw.dedupped_ident)
                    self._unique_runways.append(rw)
        return self._unique_runways
    unique_runways = property(get_unique_runways)

    def _compute_cloud_ceiling(self, metar: Metar):
        ceiling = coalesce(metar.vertical_visibility, 10_000)
        for c in metar.clouds:
            if c.quantity in (CloudQuantity.BKN, CloudQuantity.OVC) and c.height <= ceiling:
                ceiling = c.height
        return ceiling

    def _compute_rw_wind(self, metar: Metar):
        """
        Returns tuple of (runway, headwind, crosswind), sorted by headwind, crosswind, only for unique runways. 
        """
        rws_wind_info = []
        rws = self.unique_runways
        rws_wind_info = sorted([RunwayWindInfo(rw, metar.wind) for rw in rws], key=lambda rwi: rwi.max_headwind, reverse=True)
        dir = rws_wind_info[0].favorable_dir
        rws_wind_info[0].is_preferred_rw_info = ("le" if dir == "calm" else dir)
        return rws_wind_info
    
    def _compute_flight_category(self, metar: Metar, ceiling: int):
        if metar is None:
            return "UNK"
        vx = self._parse_visibility(metar.visibility.distance)
        overall_flight_category = "UNK"
        vx_flight_category = "UNK"
        ceiling_flight_category = "UNK"
        for ceiling_thresh, vx_thresh, rule in FLIGHT_RULES_REQUIREMENTS:
            if overall_flight_category == "UNK" and (ceiling <= ceiling_thresh or vx <= vx_thresh):
                overall_flight_category = rule
            if ceiling_flight_category == "UNK" and (ceiling <= ceiling_thresh):
                ceiling_flight_category = rule
            if vx_flight_category == "UNK" and (vx <= vx_thresh):
                vx_flight_category = rule
        return overall_flight_category, vx_flight_category, ceiling_flight_category
    
    def _parse_visibility(self, s: str):
        if s.endswith("SM"):
            s = s[:-2].split(" ")
            if len(s) == 1:
                return float(s[0])
            else:
                f = s[1].split("/")
                return float(s[0]) + float(f[0]) / float(f[1])
        else:
            return 0
    
    def _get_cloud_ceiling(self):
        self._fetch_current_metar()
        return self._cloud_ceiling

    def _get_flight_category(self):
        self._fetch_current_metar()
        return self._flight_category
    
    def _get_vx_flight_category(self):
        self._fetch_current_metar()
        return self._vx_flight_category
    
    def _get_ceiling_flight_category(self):
        self._fetch_current_metar()
        return self._ceiling_flight_category

    def _get_runway_wind_info(self):
        self._fetch_current_metar()
        return self._runway_wind_info
    
    def _fetch_current_metar(self, check_cache=True, cache_expiration_timeout=60):
        """Fetch current METAR and cache relevant data with an expiration time in seconds"""
        t = time.time()
        if (not check_cache) or (self._last_metar_fetch_time is None) or (self._metar is None) or (t - self._last_metar_fetch_time > cache_expiration_timeout):
            self._last_metar_fetch_time = t
            new_metar = fetch_latest_metar(coalesce(self.icao_code, self.ident))
            # Only update & recompute if METAR is a new time
            if self._metar is None or new_metar.day != self._metar.day or new_metar.time != self._metar.time:
                self._metar = new_metar
                if self._metar is not None:
                    self._cloud_ceiling = self._compute_cloud_ceiling(self._metar)
                    self._runway_wind_info = self._compute_rw_wind(self._metar)
                    self._flight_category, self._vx_flight_category, self._ceiling_flight_category = self._compute_flight_category(self._metar, self._cloud_ceiling)
        return self._metar
    metar: Metar = property(_fetch_current_metar)
    cloud_ceiling: int = property(_get_cloud_ceiling)
    runway_wind_info: RunwayWindInfo = property(_get_runway_wind_info)
    flight_category: str = property(_get_flight_category)
    visibility_flight_category: str = property(_get_vx_flight_category)
    ceiling_flight_category: str = property(_get_ceiling_flight_category)
    
    def _fetch_current_taf(self, check_cache=True, cache_expiration_timeout=60):
        """Fetch current TAF and cache relevant data with an expiration time in seconds"""
        t = time.time()
        if (not check_cache) or (self._last_metar_fetch_time is None) or (self._metar is None) or (t - self._last_metar_fetch_time > cache_expiration_timeout):
            self._taf = "TAF TODO"
        return self._taf
    taf = property(_fetch_current_taf)
    
def _prefetch_azos_airport_info(check_cache=True):
    """Fetches & caches airport info AZOS geojson & returns all airport FAA LIDs / ICAO codes"""
    # Cache check
    fp = config["azos_airport_info_fp"]
    geojson_fp = f"{fp}/AZOS.geojson"
    if (not check_cache) or (not os.path.isfile(geojson_fp)):
        resp = httpx.get("http://mesonet.agron.iastate.edu/geojson/network/AZOS.geojson", timeout=60)
        geojson = resp.json()
        with open(geojson_fp, "w") as f:
            json.dump(geojson, f)
    with open(geojson_fp) as f:
        g = json.load(f)

    # Save airports
    for r in g["features"]:
        code = r["id"]
        airport_fp = f"{fp}/{code}.json"
        if not os.path.isfile(airport_fp):
            with open(airport_fp, "w") as f:
                json.dump(r, f)

    return [r["id"] for r in g["features"]]

with open(os.path.join(config["keys_fp"], config["airportdb_token_fn"]), "r") as f:
    AIRPORTDB_KEY = f.read()

_prefetch_azos_airport_info()

# Cache for airport info
_AIRPORTS = dict()

def _fetch_airportdb_airport_info(icao_code, check_cache=True):
    json_dir = config["airportdb_airport_info_fp"]
    json_fp = f"{json_dir}/{icao_code}.json"
    if (not check_cache) or (not os.path.isfile(json_fp)):
        url = f"https://airportdb.io/api/v1/airport/{icao_code}?apiToken={AIRPORTDB_KEY}"
        resp = httpx.get(url, timeout=60)
        if resp.status_code == 404:
            return None
        airport_info = resp.json()
        with open(json_fp, "w") as f:
            json.dump(airport_info, f)
    with open(json_fp) as f:
        info = json.load(f)
        return Airport(
            ident=info["ident"],
            icao_code=info["icao_code"],
            iata_code=info["iata_code"],
            local_code=info["local_code"],
            lat=coalesce_float(info["latitude_deg"]),
            long=coalesce_float(info["longitude_deg"]),
            elevation_ft=info["elevation_ft"],
            iso_country=info["iso_country"],
            runways=[Runway(
                length_ft=coalesce_int_from_float(r["length_ft"]),
                width_ft=coalesce_int_from_float(r["width_ft"]),
                surface=r["surface"],
                lighted=r["lighted"] == "1",
                closed=r["closed"] == "1",
                le_ident=r["le_ident"],
                le_elevation_ft=coalesce_int_from_float(r["le_elevation_ft"]),
                le_heading_degT=coalesce_int_from_float(r["le_heading_degT"]),
                le_displaced_threshold_ft=coalesce_int_from_float(r["le_displaced_threshold_ft"]),
                he_ident=r["he_ident"],
                he_elevation_ft=coalesce_int_from_float(r["he_elevation_ft"]),
                he_heading_degT=coalesce_int_from_float(r["he_heading_degT"]),
                he_displaced_threshold_ft=coalesce_int_from_float(r["he_displaced_threshold_ft"])
            ) for r in info["runways"]],
            frequencies=[Frequency(
                airport_ident=f["airport_ident"],
                type=f["type"],
                description=f["description"],
                frequency_mhz=f["frequency_mhz"]
            ) for f in info["freqs"]]
        )

def _fetch_azos_airport_info(icao_like_code):
    ident = icao_to_local(icao_like_code)
    fp = f"{config['azos_airport_info_fp']}/{ident}.json"
    if not os.path.isfile(fp):
        return None
    with open(fp) as f:
        info = json.load(fp)
    return Airport(
        ident=icao_like_code,
        icao_code=icao_like_code if icao_like_code == ident else None,
        local_code=ident if icao_like_code != ident else ident,
        lat=coalesce_float(info["geometry"]["coordinates"][0]),
        long=coalesce_float(info["geometry"]["coordinates"][1]),
        elevation_ft=int(coalesce_float(info["properties"]["elevation"], default=0)),
        iso_country=info["properties"]
    )

def _set_airport_info(icao_like_code, info):
    """Set cache to airport info, return true if successful and info not null"""
    if info is not None:
        _AIRPORTS[icao_like_code] = info
        return True
    return False

def get_airport_info(icao_like_code, check_cache=True):
    """Get airport info from ICAO code (will auto correct ICAO) using existing cache"""
    icao_like_code = icao_like_code.upper()
    if (not check_cache) or icao_like_code in _AIRPORTS.keys():
        return _AIRPORTS[icao_like_code]
    
    # Try airportdb
    info = _fetch_airportdb_airport_info(icao_like_code, check_cache=check_cache)
    if _set_airport_info(icao_like_code, info):
        return info

    # Try airportdb with K appended
    icao = try_append_k(icao_like_code)
    if icao:
        info = _fetch_airportdb_airport_info(f"K{icao_like_code}", check_cache=check_cache)
        if _set_airport_info(icao_like_code, info):
            return info

    # Fallback to azos - will auto convert to local if needed
    info = _fetch_azos_airport_info(icao_like_code)
    if _set_airport_info(icao_like_code, info):
        return info
    return None

def icao_to_local(icao):
    icao = icao.lower()
    if icao.startswith("k") and len(icao) == 4:
        return icao[1:]
    
def try_append_k(icao_like_code):
    icao_like_code = icao_like_code.lower()
    return f"K{icao_like_code}" if (not icao_like_code.startswith("k")) and len(icao_like_code) == 3 else None
