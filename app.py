import os
import time

from flask import Flask, render_template, send_from_directory, send_file
from flask_sock import Sock

from airport_info import get_airport_info
from aviation_weather import fetch_compute_historical_metar, fetch_cached_historical_metar
from render import render_metar_wind, render_metar_additional_info, render_metar_cloud_cover
from utils import coalesce

app = Flask(__name__)

sock = Sock()
sock.init_app(app)

if app.debug:
    print(f"FLASK DEBUG MODE ENABLED - GPIO SET TO MOCK")
    os.environ["GPIOZERO_PIN_FACTORY"] = os.environ.get("GPIOZERO_PIN_FACTORY", "mock")
else:
    print(f"FLASK PROD MODE ENABLED - GPIO SET TO HARDWARE")

from gpio_flask import flask_gpio_manager
flask_gpio_manager.debug = app.debug

TEST_ICAOS = [
    "ksfo",
    "ksck",
    "ksql",
    "sfo",
    "sck",
    "sql"
]
# for a in TEST_ICAOS:
#     print(f"http://127.0.0.1:5000/metar/{a}")
print("http://127.0.0.1:5000/historical_metar_chart/kcle")

@app.route("/socket_testing/<icao>")
def testing_icao(icao):
    airport = get_airport_info(icao)
    metar = airport.metar
    taf = airport.taf
    return render_template("socket_testing.html", 
                           debug_info="DEBUG" if app.debug else "PROD",
                           metar=metar,
                           taf=taf)

@app.route("/historical_metar_chart/<icao>")
def historical_metar_chart(icao):
    return render_template("historical_metar_chart.html",
                           icao=icao)

# Fetch currently computed historical METAR - returns cached results only
@app.route("/historical_metar_chart_data/<icao>")
def historical_metar_chart_data(icao):
    df = fetch_cached_historical_metar(get_airport_info(icao).icao_code)
    return "" if df is None else df.to_string()

# Fetch compute historical METAR - will skip if cache hit
@app.route("/historical_metar_fetch_compute/<icao>")
def historical_metar_chart_fetch_compute(icao):
    st = time.time()
    fetch_compute_historical_metar(get_airport_info(icao))
    return str(time.time() - st)

@app.route("/metar/<icao>")
def image_testing(icao):
    # TODO add a text box at the top for the metar text & recency, in courier
    # TODO update rendering cache here
    # TODO render cloud coverage - depict as a simple rectangular bar with shading to indicate layers & text next to it
    airport = get_airport_info(icao)
    return render_template("metar.html", 
                           icao=icao,
                           metar=airport.metar.message)

@app.route("/dynamicassets/metar_wind/<icao>.svg")
def dynamicassets_metar_wind(icao):
    airport = get_airport_info(icao)
    wind_buffer = render_metar_wind(airport)

    return send_file(
        wind_buffer,
        as_attachment=True,
        download_name=f"{icao}_wind.svg",
        mimetype="image/svg+xml"
    )

@app.route("/dynamicassets/metar_additional_info/<icao>.svg")
def dynamicassets_metar_additional_info(icao):
    airport = get_airport_info(icao)
    additional_info_buffer = render_metar_additional_info(airport)
    return send_file(
        additional_info_buffer,
        as_attachment=True,
        download_name=f"{icao}_metar_info.svg",
        mimetype="image/svg+xml"
    )

@app.route("/dynamicassets/metar_cloud_cover/<icao>.svg")
def dynamicassets_metar_cloud_cover(icao):
    cloud_cover_buffer = render_metar_cloud_cover()
    return send_file(
        cloud_cover_buffer,
        as_attachment=True,
        download_name=f"{icao}_metar_cloud_cover.svg",
        mimetype="image/svg+xml"
    )

@app.route("/favicon.ico")
def favicon():
    return send_from_directory(os.path.join(app.root_path, "static"), "favicon.ico", mimetype="image/vnd.microsoft.icon")

@app.route("/")
def root():
    return "I love monkeys."

@sock.route("/echo")
def echo(ws):
    fgm = flask_gpio_manager
    fgm.send_gpio_state(ws, app.debug)
    while True:
        data = ws.receive()
        fgm.read_client_commands(data)
        fgm.send_gpio_state(ws, app.debug)