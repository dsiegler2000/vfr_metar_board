import requests
import urllib.parse
from metar_taf_parser.parser.parser import MetarParser, TAFParser

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
AVIATIONWEATHER_TAF_API_URL = "https://aviationweather.gov/api/data/taf"

def aviationweather_api_request(url, **params):
    full_url = f"{url}?{urllib.parse.urlencode(params)}"
    print(full_url)
    response = requests.get(full_url)
    print(response)

    if response is None or response.status_code != 200:
        print(f"Request to {full_url} returned status code {response.status_code}")

    return response.text

def fetch_latest_metar(icao_id, madis=False, retry_kilo=True):
    if madis:
        raise ValueError("MADIS METAR is not currently supported")
    metar_text = aviationweather_api_request(AVIATIONWEATHER_METAR_API_URL, 
                                             ids=icao_id)
    try: 
        metar = MetarParser().parse(metar_text)
        return metar.message
    except:
        if retry_kilo:
            return fetch_latest_metar(icao_id, retry_kilo=False)
        return ""

def fetch_latest_taf(icao_like_id, retry_kilo=True):
    icao_like_id = icao_like_id.lower()
    taf_text = aviationweather_api_request(AVIATIONWEATHER_TAF_API_URL, 
                                           ids=icao_like_id)
    # try:
    print(taf_text)
    taf = TAFParser().parse(taf_text)
    # return taf.message
    return taf_text
    # except:
    #     if retry_kilo and (not (icao_like_id.startswith("k") and len(icao_like_id) == 4)):
    #         return fetch_latest_taf("k" + icao_like_id, retry_kilo=False)
    #     return ""

# %%
taf = """
KSFO 110520Z 1106/1212 29025G35KT P6SM FEW200 
  FM110700 29015G25KT P6SM FEW015 BKN250 
  FM111500 26012KT P6SM OVC015 
  FM111900 27017KT P6SM SCT025 BKN250 
  FM112100 26020G28KT P6SM OVC250 
  FM120400 26018KT P6SM FEW250 
  FM120600 23010KT P6SM -SHRA BKN030
"""

# TODO debug why the taf parser isn't working... invalid format?
# ...     'TAF LFPG 150500Z 1506/1612 17005KT 6000 SCT012 TEMPO 1506/1509 3000 BR BKN006 PROB40 TEMPO 1506/1508 0400 BCFG BKN002 PROB40 TEMPO 1512/1516 4000 -SHRA FEW030TCU BKN040 BECMG 1520/1522 CAVOK TEMPO 1603/1608 3000 BR BKN006 PROB40 TEMPO 1604/1607 0400 BCFG BKN002 TX17/1512Z TN07/1605Z')