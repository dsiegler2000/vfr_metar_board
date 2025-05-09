import requests
import urllib.parse
from metar_taf_parser.parser.parser import MetarParser

"""
Relevant functions to pull observations, forecasts, & historical weather data. 
Below shows product & API source
- METAR (current)       https://aviationweather.gov/api/data/metar
- METAR (historical)
- TAF 
- GFA
- MOS 
- Daily
Any other weather observations I'm missing (AIRMET, SIGMET)
Check aviationweather & foreflight
"""

# API URLs
AVIATIONWEATHER_METAR_API_URL = "https://aviationweather.gov/api/data/metar"

def aviationweather_api_request(url, **params):
    full_url = f"{url}?{urllib.parse.urlencode(params)}"
    response = requests.get(full_url)

    if response is None or response.status_code != 200:
        print(f"Request to {full_url} returned status code {response.status_code}")

    return response.text

def fetch_latest_metar(icao_id, madis=False):
    if madis:
        raise ValueError("MADIS METAR is not currently supported")
    metar_text = aviationweather_api_request(AVIATIONWEATHER_METAR_API_URL, 
                                             ids=icao_id)
    metar = MetarParser().parse(metar_text)
    print(metar_text)
    return metar.message
