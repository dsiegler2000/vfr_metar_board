import json 
import os
import httpx
from config import config

class Airport:
    """Airport info & utility functions constructed from AZOS json info file"""
    def __init__(self, faa_lid):
        faa_lid = faa_lid.lower()
        fp = f"{config['airport_info_fp']}/{faa_lid}.json"

def fetch_azos_geojson_airport_info():
    """Fetches & caches airport info AZOS geojson & returns all airport FAA LID"""
    # Cache check
    fp = config["airport_info_fp"]
    geojson_fp = f"{fp}/AZOS.geojson"
    if not os.path.isfile(geojson_fp):
        resp = httpx.get("http://mesonet.agron.iastate.edu/geojson/network/AZOS.geojson", timeout=60)
        geojson = resp.json()
        with open(geojson_fp, "w") as f:
            json.dump(geojson, f)
    with open(geojson_fp) as f:
        g = json.load(f)

    # Save airports
    for r in g["features"]:
        faa_lid = r["id"]
        airport_fp = f"{fp}/{faa_lid}.json"
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

AIRPORTS = {a: None for a in fetch_azos_geojson_airport_info()}

def get_airport_info(faa_lid):
    """Get airport info from FAA LID (will auto correct ICAO)"""
    faa_lid = autocorrect_icao(faa_lid)
    if faa_lid not in AIRPORTS.keys():
        raise ValueError("Invalid airport code!")
    if AIRPORTS[faa_lid] is None:
        AIRPORTS[faa_lid] = Airport(faa_lid)

def autocorrect_icao(airport_id):
    airport_id = airport_id.lower()
    if airport_id.startswith("k") and len(airport_id) == 4:
        return airport_id[1:]
    
# re-write this using api