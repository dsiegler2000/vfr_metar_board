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
import warnings
warnings.simplefilter(action="ignore", category=FutureWarning)

import requests
import httpx
import os

from functools import partial
import urllib.parse
import re
import time
from datetime import datetime
import pandas as pd
import numpy as np
from io import StringIO

from metar_taf_parser.parser.parser import MetarParser, TAFParser
from metar_taf_parser.model.model import Metar
from metar_taf_parser.model.enum import Phenomenon

from config import config
from utils import coalesce

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from airport_info import Airport

# API URLs
AVIATIONWEATHER_METAR_API_URL = "https://aviationweather.gov/api/data/metar"
AVIATIONWEATHER_TAF_API_URL = "https://aviationweather.gov/api/data/taf"

HISTORICAL_WEATHER_STATS_FP = config["historical_weather_stats_fp"]

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

def mesonet_asos_request(icao_like_code: str, dt1: datetime, dt2: datetime):
    icao_like_code = icao_like_code.upper()
    uri = (
        "http://mesonet.agron.iastate.edu/cgi-bin/request/asos.py?"
        f"station={icao_like_code}"
        f"&year1={dt1.year}&month1={dt1.month}&day1={dt1.day}"
        f"&year2={dt2.year}&month2={dt2.month}&day2={dt2.day}"
        "&data=all&direct=yes&latlon=no&elev=no&missing=M&trace=T&Etc%2FUTC&format=onlycomma&report_type=1&report_type=3&report_type=4"
    )
    print(f"Requesting historical METAR data for {icao_like_code} from {dt1} to {dt2}\nuri={uri}")
    response = httpx.get(uri, timeout=60 * 5)
    if response is None or response.status_code != 200:
        print(f"Error requesting historical METAR data for {icao_like_code}: {response.status_code}")
        return None
    text = response.text
    df = pd.read_csv(StringIO(text), low_memory=False)
    if df.shape[0] == 0:
        return None
    return df

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

def fetch_last_week_metar():
    pass

def fetch_cached_historical_metar(airport: Airport, retry_kilo: bool=True):
    """Fetches already computed & cached historical METAR data"""
    pass

def fetch_compute_historical_metar(airport: Airport, check_cache: bool=True, retry_kilo: bool=True, start_year: int=2016, end_year: int=2025):
    """Fetches & computes historical METAR data"""
    # TODO fetch & process historical data for fast access in the future

    # TODO implement retry no kilo
    # TODO implement cache - likely move the logic into a helper
    # TODO implement this on a yearly basis, so then the computation isn't as much
    # TODO compute percentiles P10, P25, etc
    # TODO properly implement the async nature of fetch_cached vs fetch_compute
    #  Have the client make a silent request to fetch_compute & fetch_cached at the same time
    # TODO make more efficient

    fp = f"{HISTORICAL_WEATHER_STATS_FP}/{airport.icao_code}.csv"
    if check_cache and os.path.isfile(fp):
        print(f"Cache hit!")
    else:
        final_df = []
        for year in range(start_year, end_year + 1):
            ident = airport.icao_code
            print(f"Fetching & computing historicals for {ident} {year}")
            st = time.time()
            df = mesonet_asos_request(ident, dt1=datetime(year, 1, 1), dt2=datetime(year, 12, 1))
            if df is None and retry_kilo:
                if ident.lower().startswith("k") and len(ident) == 4:
                    ident = ident[1:]
                elif len(ident) == 3:
                    ident = f"K{ident.upper()}"
                df = mesonet_asos_request(ident, dt1=datetime(start_year, 1, 1), dt2=datetime(start_year, 12, 1))

            print(f"Downloaded {df.shape[0]} rows in {time.time() - st:2.2f}s")
            st = time.time()
            print("Parsing data...")

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

            # Add appropriate timing columns
            df["dt"] = pd.to_datetime(df["dt"])
            df["hour"] = df["dt"].dt.hour
            df["date"] = df["dt"].dt.date
            df["month"] = df["dt"].dt.month
            df["year"] = df["dt"].dt.year
            df["month_dt"] = df["dt"].apply(lambda t: t.replace(day=1, hour=0, minute=0, second=0, microsecond=0))


            # Reduce data to only the relevant observation for the hour
            # The first manual (non-AUTO) observation or first AUTO observation if no manual exists
            df["auto_metar"] = df["metar"].str.contains(r"AUTO|MADISHF")
            df = df.loc[df.groupby(["date", "hour", "auto_metar"])["dt"].idxmin()].groupby(["date", "hour"]).first()

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

                r["metar_obj"] = m
                r["min_headwind"] = rwi[0]
                r["max_headwind"] = rwi[1]
                r["min_crosswind"] = rwi[2]
                r["max_crosswind"] = rwi[3]

                r["cloud_ceiling"] = cloud_ceiling
                r["visibility"] = visibility
                r["temp_c"] = m.temperature
                r["dewpoint_c"] = m.dew_point
                r["pressure_in"] = m.altimeter
                if m.wind is not None:
                    r["wind_dir_true"] = coalesce(m.wind.degrees, r["wind_dir_true"])
                    r["wind_str"] = coalesce(m.wind.speed, r["wind_str"])
                    r["wind_gust"] = coalesce(m.wind.gust, r["wind_gust"])
                for p in HISTORIC_WEATHER_PHENOMENONS:
                    r[repr(p)] = p in phenomenons_list

                return r

            df = df.apply(clean_data, axis=1)

            # TODO implement data quality checks
            def pct(rows, target_val=True):
                return (rows == target_val).sum() / rows.shape[0]

            def safe_mean(rows, to_replace="M"):
                return np.mean(pd.to_numeric(rows.replace(to_replace, np.nan), errors="coerce"))
            
            def percentile(rows, ptile, to_replace="M"):
                return np.percentile(pd.to_numeric(rows.replace(to_replace, np.nan), errors="coerce"), q=ptile)

            # Ok, so we want to do aggregations by row here
            stats_df = df.groupby(["year", "month", "hour"]).agg({
                "temp_f":           [safe_mean, partial(percentile, ptile=25), partial(percentile, ptile=50), partial(percentile, ptile=75)],
                "dewpoint_f":       [safe_mean, partial(percentile, ptile=25), partial(percentile, ptile=50), partial(percentile, ptile=75)],
                "wind_dir_true":    [safe_mean],
                "wind_str":         [safe_mean, partial(percentile, ptile=25), partial(percentile, ptile=50), partial(percentile, ptile=75)],
                "wind_gust":        [safe_mean, partial(percentile, ptile=25), partial(percentile, ptile=50), partial(percentile, ptile=75), partial(pct, target_val="M")],
                "pressure_in":      [safe_mean, partial(percentile, ptile=25), partial(percentile, ptile=50), partial(percentile, ptile=75)],
                "visibility":       [safe_mean, partial(percentile, ptile=25), partial(percentile, ptile=50), partial(percentile, ptile=75)],
                "min_headwind":     [safe_mean, partial(percentile, ptile=25), partial(percentile, ptile=50), partial(percentile, ptile=75)],
                "max_headwind":     [safe_mean, partial(percentile, ptile=25), partial(percentile, ptile=50), partial(percentile, ptile=75)],
                "min_crosswind":    [safe_mean, partial(percentile, ptile=25), partial(percentile, ptile=50), partial(percentile, ptile=75)],
                "max_crosswind":    [safe_mean, partial(percentile, ptile=25), partial(percentile, ptile=50), partial(percentile, ptile=75)],
                "cloud_ceiling":    [safe_mean, partial(percentile, ptile=25), partial(percentile, ptile=50), partial(percentile, ptile=75)],
            } | {repr(p):           [np.mean] for p in HISTORIC_WEATHER_PHENOMENONS})
            final_df.append(stats_df)
            print(f"Computed stats over {stats_df.shape[0]} in {time.time() - st:2.2f}s")
        final_df = pd.concat(final_df)
        final_df.to_csv(fp)
