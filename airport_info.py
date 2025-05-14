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

from utils import coalesce_int_from_float, coalesce_float, coalesce
from metar_taf_parser.model.model import Wind

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

    def __init__(self, runway: Runway, wind: Wind, is_preferred_rw_info: Literal["le", "he", "no", "unk"]="unk", fast_compute: bool=False):
        # TODO add fast computation mode that doesn't consider wind variation for speeding up historical computations
        if fast_compute:
            raise ValueError("fast_compute is not yet supported!")
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
    """Airport info & utility functions constructed from raw info"""
    ident: str
    icao_code: str
    iata_code: str
    local_code: str
    lat: float
    long: float
    elevation_ft: int
    iso_country: str
    runways: list
    frequencies: list

    _unique_runways = None
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

    def compute_rw_wind(self, metar, unique_rws_only=True):
        """
        Returns tuple of (runway, headwind, crosswind), sorted by headwind, crosswind. 
        """
        rws_wind_info = []
        rws = self.unique_runways if unique_rws_only else self.runways
        rws_wind_info = sorted([RunwayWindInfo(rw, metar.wind) for rw in rws], key=lambda rwi: rwi.max_headwind, reverse=True)
        dir = rws_wind_info[0].favorable_dir
        rws_wind_info[0].is_preferred_rw_info = ("le" if dir == "calm" else dir)
        return rws_wind_info
        
def prefetch_azos_airport_info(check_cache=True):
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

with open(config["airportdb_token_fp"], "r") as f:
    AIRPORTDB_KEY = f.read()

prefetch_azos_airport_info()

# Cache for airport info
AIRPORTS = dict()

def fetch_airportdb_airport_info(icao_code, check_cache=True):
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

def fetch_azos_airport_info(icao_like_code):
    ident = autocorrect_icao(icao_like_code)
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

def set_airport_info(icao_like_code, info):
    """Set cache to airport info, return true if successful and info not null"""
    if info is not None:
        AIRPORTS[icao_like_code] = info
        return True
    return False

def get_airport_info(icao_like_code, check_cache=True):
    """Get airport info from ICAO code (will auto correct ICAO) using existing cache"""
    icao_like_code = icao_like_code.upper()
    if icao_like_code in AIRPORTS.keys() and (not check_cache):
        return AIRPORTS[icao_like_code]
    
    # Try airportdb
    info = fetch_airportdb_airport_info(icao_like_code, check_cache=check_cache)
    if set_airport_info(icao_like_code, info):
        return info

    # Try airportdb with K appended
    info = fetch_airportdb_airport_info(f"K{icao_like_code}", check_cache=check_cache)
    if set_airport_info(icao_like_code, info):
        return info

    # Fallback to azos
    info = fetch_azos_airport_info(icao_like_code)
    if set_airport_info(icao_like_code, info):
        return info
    return None

def autocorrect_icao(airport_id):
    airport_id = airport_id.lower()
    if airport_id.startswith("k") and len(airport_id) == 4:
        return airport_id[1:]
