import os
import time

from flask import Flask, render_template, send_from_directory, send_file
from flask_sock import Sock
from werkzeug.wsgi import FileWrapper

import airport_info as airports
import aviation_weather as weather
from render import render_metar_wind, render_metar_additional_info

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
for a in TEST_ICAOS:
    print(f"http://127.0.0.1:5000/metar/{a}")

@app.route("/testing/<icao>")
def testing_icao(icao):
    metar = weather.fetch_latest_metar(icao)
    taf = weather.fetch_latest_taf(icao)
    return render_template("index.html", 
                           debug_info="DEBUG" if app.debug else "PROD",
                           metar=metar,
                           taf=taf)

@app.route("/metar/<icao>")
def image_testing(icao):
    # TODO add a text box at the top for the metar text, in courier
    # TODO update cache here
    return render_template("metar.html", 
                           icao=icao)

@app.route("/dynamicassets/metar_wind/<icao>.svg")
def dynamicassets_metar_wind(icao):
    airport = airports.get_airport_info(icao)
    wind_buffer = render_metar_wind(airport)

    # TODO render cloud coverage - depict as a simple rectangular bar with shading to indicate layers & text next to it
    return send_file(
        wind_buffer,
        as_attachment=True,
        download_name=f"{icao}_wind.svg",
        mimetype="image/svg+xml"
    )

@app.route("/dynamicassets/metar_additional_info/<icao>.svg")
def dynamicassets_metar_additional_info(icao):
    # TODO this is inefficient - cache by minute!
    airport = airports.get_airport_info(icao)
    additional_info_buffer = render_metar_additional_info(airport)
    return send_file(
        additional_info_buffer,
        as_attachment=True,
        download_name=f"{icao}_metar_info.svg",
        mimetype="image/svg+xml"
    )

def dynamicassets_metar_cloudcover():
    pass

@app.route("/favicon.ico")
def favicon():
    return send_from_directory(os.path.join(app.root_path, "static"), "favicon.ico", mimetype="image/vnd.microsoft.icon")

@app.route("/")
def root():
    return "Boop."

@sock.route("/echo")
def echo(ws):
    fgm = flask_gpio_manager
    fgm.send_gpio_state(ws, app.debug)
    while True:
        data = ws.receive()
        fgm.read_client_commands(data)
        fgm.send_gpio_state(ws, app.debug)