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
import httpx
import urllib.parse
import re
import time
import pandas as pd
from io import StringIO
from datetime import datetime
from metar_taf_parser.parser.parser import MetarParser, TAFParser

# API URLs
AVIATIONWEATHER_METAR_API_URL = "https://aviationweather.gov/api/data/metar"
AVIATIONWEATHER_TAF_API_URL = "https://aviationweather.gov/api/data/taf"

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
    icao_like_id = icao_like_id.lower()

    # TODO implement retry no kilo
    # TODO implement cache - likely move the logic into a helper
    # TODO implement this on a yearly basis, so then the computation isn't as much

    dt1 = datetime.strptime("2024-01-01", "%Y-%m-%d")
    dt2 = datetime.strptime("2024-12-31", "%Y-%m-%d")
    uri = (
        "http://mesonet.agron.iastate.edu/cgi-bin/request/asos.py?"
        f"station={icao_like_id.upper()}"
        f"&year1={dt1.year}&month1={dt1.month}&day1={dt1.day}"
        f"&year2={dt2.year}&month2={dt2.month}&day2={dt2.day}"
        "&data=all&direct=yes&latlon=no&elev=no&missing=M&trace=T&Etc%2FUTC&format=onlycomma&report_type=1&report_type=3&report_type=4"
    )
    print("start waiting...")
    st = time.time()
    response = httpx.get(uri, timeout=60 * 5)
    text = response.text
    df = pd.read_csv(StringIO(text))
    print("time to fetch:")
    print(time.time() - st)
    print(f"fetched: {df.shape[0]} rows")
    st = time.time()
    print("parsing")
    df["metar"].apply(lambda metar: MetarParser().parse(metar))
    print(time.time() - st)
    # print(df.head())
    # TODO from this, compute & store the monthly...
    #  p10, p25, p50, p75, p90, average days


def fetch_parse_historical_weather(icao_like_id: str, retry_no_kilo: bool=True, check_cache: bool=True):
    """

    """
    pass