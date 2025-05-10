"""
ICAO codes will be default respected, with fallback to FAA LID
"""

import json 
import os
import httpx
from config import config
from dataclasses import dataclass
from utils import coalesce_int, coalesce_float

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
    pass

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

@dataclass
class Frequency:
    airport_ident: str
    type: str
    description: str
    frequency_mhz: str

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
    g_df = pd.DataFrame.from_dict({
        r["id"]: [
            r["geometry"]["coordinates"][0],
            r["geometry"]["coordinates"][1],
            r["properties"]["sname"],
            r["properties"]["elevation"],
            r["properties"]["archive_begin"],
            r["properties"]["archive_end"],
            r["properties"]["state"],
            r["properties"]["country"],
            r["properties"]["tzname"],
            r["properties"]["online"]
        ] for r in g["features"]
    }, orient="index", columns=[
        "lat", 
        "long", 
        "name",
        "elevation",
        "archive_begin",
        "archive_end",
        "state",
        "country",
        "tzname",
        "online",
    ])
    g_df.to_csv(csv_fp)
    return g_df

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
        print(url)
        resp = httpx.get(url, timeout=60)
        if resp.status_code == 404:
            return None
        airport_info = resp.json()
        if not os.path.exists(json_dir):
            os.makedirs(json_dir)
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
                length_ft=coalesce_int(r["length_ft"]),
                width_ft=coalesce_int(r["width_ft"]),
                surface=r["surface"],
                lighted=r["lighted"] == "1",
                closed=r["closed"] == "1",
                le_ident=r["le_ident"],
                le_elevation_ft=coalesce_int(r["le_elevation_ft"]),
                le_heading_degT=coalesce_int(r["le_heading_degT"]),
                le_displaced_threshold_ft=coalesce_int(r["le_displaced_threshold_ft"]),
                he_ident=r["he_ident"],
                he_elevation_ft=coalesce_int(r["he_elevation_ft"]),
                he_heading_degT=coalesce_int(r["he_heading_degT"]),
                he_displaced_threshold_ft=coalesce_int(r["he_displaced_threshold_ft"])
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
    
# re-write this using api