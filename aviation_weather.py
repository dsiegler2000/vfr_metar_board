"""
Relevant functions to pull observations, forecasts, & historical weather data. 
Below shows product & API source
- METAR (current)       https://aviationweather.gov/api/data/metar
- METAR (historical)
- TAF                   https://aviationweather.gov/api/data/taf
- GFA
- MOS 
- Daily
Any other weather observations I'm missing (AIRMET, SIGMET)
Check aviationweather & foreflight
"""

import requests
import urllib.parse
import re
from metar_taf_parser.parser.parser import MetarParser, TAFParser
from metar_taf_parser.parser import parser

# API URLs
AVIATIONWEATHER_METAR_API_URL = "https://aviationweather.gov/api/data/metar"
AVIATIONWEATHER_TAF_API_URL = "https://aviationweather.gov/api/data/taf"

# TODO create extended version of metar that includes vfr, ifr, lifr, etc
#  or maybe just have this as functional extensions of the existing class...
class Metar():
    pass

def aviationweather_api_request(url: str, **params):
    full_url = f"{url}?{urllib.parse.urlencode(params)}"
    response = requests.get(full_url)

    if response is None or response.status_code != 200:
        print(f"Request to {full_url} returned status code {response.status_code}")

    return response.text

def fetch_latest_metar(icao_like_id: str, madis: bool=False, retry_kilo: bool=True):
    if madis:
        raise ValueError("MADIS METAR is not currently supported")
    icao_like_id = icao_like_id.lower()
    metar_text = aviationweather_api_request(AVIATIONWEATHER_METAR_API_URL, 
                                             ids=icao_like_id)
    try: 
        metar = MetarParser().parse(metar_text)
        return metar
    except:
        if retry_kilo and (not (icao_like_id.startswith("k") and len(icao_like_id) == 4)):
            return fetch_latest_metar("k" + icao_like_id, retry_kilo=False)
        return None

def fetch_latest_taf(icao_like_id: str, retry_kilo: bool=True):
    icao_like_id = icao_like_id.lower()
    taf_text = aviationweather_api_request(AVIATIONWEATHER_TAF_API_URL, 
                                           ids=icao_like_id)
    
    # Clean TAF string
    taf_text = re.sub(r"\s+", " ", taf_text).strip().replace("\n", "").upper()

    # Append TAF identifier if not included
    if not taf_text.startswith("TAF"):
        taf_text = f"TAF {taf_text}"

    try:
        taf = TAFParser().parse(taf_text)
        return taf.message
    except:
        if retry_kilo and (not (icao_like_id.startswith("k") and len(icao_like_id) == 4)):
            return fetch_latest_taf("k" + icao_like_id, retry_kilo=False)
        return ""
    
def fetch_historical_metar(icao_like_id: str, retry_no_kilo: bool=True, check_cache: bool=True):
    # TODO fetch & process historical data for fast access in the future
    # need to be mindful of memory requirements - ksck has 5m reports & going back to mid 2016, the file size is 167mb
    # can mostly copy previous code
    # note the code should be local & UPPER CASE 
    # SCK NOT sck or ksck or KSCK
    pass
