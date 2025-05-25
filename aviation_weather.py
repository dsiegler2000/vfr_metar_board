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

from __future__ import annotations
import requests
import httpx
import urllib.parse
import re
import time
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from metar_taf_parser.parser.parser import MetarParser, TAFParser
from metar_taf_parser.model.model import Metar
from metar_taf_parser.model.enum import Phenomenon

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from airport_info import Airport

# API URLs
AVIATIONWEATHER_METAR_API_URL = "https://aviationweather.gov/api/data/metar"
AVIATIONWEATHER_TAF_API_URL = "https://aviationweather.gov/api/data/taf"

HISTORIC_WEATHER_PHENOMENONS = [
    Phenomenon.RAIN,
    Phenomenon.DRIZZLE,
    Phenomenon.SNOW,
    Phenomenon.SNOW_GRAINS,
    Phenomenon.UNKNOW_PRECIPITATION,
    Phenomenon.FOG,
    Phenomenon.MIST,
    Phenomenon.HAZE
]

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
    
def fetch_historical_metar(airport: Airport, check_cache: bool=True, start_ds: str="2024-01-01", end_ds: str="2024-12-31"):
    # TODO fetch & process historical data for fast access in the future
    # need to be mindful of memory requirements - ksck has 5m reports & going back to mid 2016, the file size is 167mb
    # can mostly copy previous code
    # note the code should be local & UPPER CASE 
    # SCK NOT sck or ksck or KSCK

    # TODO implement retry no kilo
    # TODO implement cache - likely move the logic into a helper
    # TODO implement this on a yearly basis, so then the computation isn't as much
    # TODO really we want to start this fetching & computation while the metar is loading
    # TODO all the calculations can be made much more efficient, & with much less memory swap

    dt1 = datetime.strptime(start_ds, "%Y-%m-%d")
    dt2 = datetime.strptime(end_ds, "%Y-%m-%d")
    uri = (
        "http://mesonet.agron.iastate.edu/cgi-bin/request/asos.py?"
        f"station={airport.icao_code.upper()}"
        f"&year1={dt1.year}&month1={dt1.month}&day1={dt1.day}"
        f"&year2={dt2.year}&month2={dt2.month}&day2={dt2.day}"
        "&data=all&direct=yes&latlon=no&elev=no&missing=M&trace=T&Etc%2FUTC&format=onlycomma&report_type=1&report_type=3&report_type=4"
    )
    print(f"Requesting historical METAR data for {airport.icao_code.upper()} from {start_ds} to {end_ds}, uri={uri}")
    st = time.time()
    # response = httpx.get(uri, timeout=60 * 5)
    # text = response.text
    # df = pd.read_csv(StringIO(text))
    # df.to_csv("data/testing.csv")
    df = pd.read_csv("data/testing.csv", index_col=0)
    print(f"Downloaded {df.shape[0]} rows in {time.time() - st:2.2f}s")
    st = time.time()
    print("parsing")
    # TODO from this, compute & store the monthly...
    #  p10, p25, p50, p75, p90, average days
    # I think best approach is
    #  keep data as a dataframe for computing monthly hourly averages
    #  then store it as a csv or json or something
    #  then when loading it / working with it live, have a wrapper class
    #  cause we may store additional info like % chance of gust, etc

    # TODO compute this for current month/year too

    df["metar_obj"] = df["metar"].apply(lambda metar: MetarParser().parse(metar))
    print("finished metar parsing")
    print(time.time() - st)
    def wind_info_apply(metar):
        rwi = airport.compute_rw_wind(metar)
        if len(rwi) > 0:
            return rwi[0].min_headwind, rwi[0].max_headwind, rwi[0].min_crosswind, rwi[0].max_crosswind
        else:
            return np.nan, np.nan, np.nan, np.nan


    # TODO this will all be covered by clean_data
    df["min_headwind"], df["max_headwind"], df["min_crosswind"], df["max_crosswind"] = zip(*df["metar_obj"].apply(wind_info_apply))
    print("finished headwind!")
    print(time.time() - st)
    df["cloud_ceiling"] = df["metar_obj"].apply(lambda metar: airport.compute_cloud_ceiling(metar))
    df["visibility"] = df["metar_obj"].apply(lambda metar: airport.parse_visibility(metar))

    df = df.rename(columns={
        "valid": "dt",
        "tmpf": "temp_f",
        "dwpf": "dewpoint_f",
        "relh": "rel_humidity",
        "drct": "wind_dir_true",
        "sknt": "wind_str",
        "p01i": "precip_1hr_ins",
        "alti": "pressure_in",
        "mslp": "pressure_mb",
        "vsby": "visibility_mi",
        "gust": "wind_gust",
        "feel": "temp_feels_like_f"
    })

    def clean_data(r):
        m = MetarParser().parse(r["metar"])
        rwi_l = airport.compute_rw_wind(m)
        rwi = (rwi_l[0].min_headwind, rwi_l[0].max_headwind, rwi_l[0].min_crosswind, rwi_l[0].max_crosswind) if len(rwi_l) > 0 else (np.nan, np.nan, np.nan, np.nan)
        cloud_ceiling = airport.compute_cloud_ceiling(m)
        visibility = airport.parse_visibility(m)
        
        # 8 of them
        phenomenons_list = set()
        for c in m.weather_conditions:
            for p in c.phenomenons:
                phenomenons_list.add(p)
        phenomenons = (p in phenomenons_list for p in HISTORIC_WEATHER_PHENOMENONS)

        return m, *rwi, cloud_ceiling, visibility, m.temperature, m.dew_point, m.wind.degrees, m.wind.speed, m.wind.gust, m.altimeter, *phenomenons

    # df[] = df.apply(clean_data, axis=1)

    df["metar_obj"], 
    df["min_headwind"],
    df["max_headwind"],
    df["min_crosswind"], 
    df["max_crosswind"], 
    df["cloud_ceiling"], 
    df["visibility"], 
    df["temp_f"], 
    df["dewpoint_f"],
    df["wind_dir_true"], 
    df["wind_str"], 
    df["wind_gust"], 
    df["pressure_in"], 
    ""

    # Add appropriate timing columns
    
    df["dt"] = pd.to_datetime(df["dt"])
    df["dt_snapped"] = df["dt"].apply(lambda t: t.replace(second=0, microsecond=0, minute=0, hour=t.hour) + timedelta(hours=t.minute // 30))
    df["hour"] = df["dt_snapped"].dt.hour
    df["month"] = df["dt"].dt.month
    df["year"] = df["dt"].dt.year
    df["month_dt"] = df["dt"].apply(lambda t: t.replace(day=1, hour=0, minute=0, second=0, microsecond=0))
    print("\n".join(df.columns))

    # TODO implement data quality checks

    df2 = df.groupby(["station", "year", "month", "hour"]).agg(
        mean_temp_f=("temp_f", "mean"),
        p50_temp_f=("temp_f", lambda t: np.quantile(50))
    )

    print(df2.head())

    print(time.time() - st)


def fetch_parse_historical_weather(icao_like_id: str, retry_no_kilo: bool=True, check_cache: bool=True):
    """

    """
    pass