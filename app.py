import time
import os

from flask import Flask, render_template
from flask_sock import Sock

import airport_info as airports
from aviation_weather import fetch_latest_metar, fetch_latest_taf

app = Flask(__name__)
# app.config["TEMPLATES_AUTO_RELOAD"] = True
# app.debug = True

sock = Sock()
sock.init_app(app)

if app.debug:
    print(f"FLASK DEBUG MODE ENABLED - GPIO SET TO MOCK")
    os.environ["GPIOZERO_PIN_FACTORY"] = os.environ.get("GPIOZERO_PIN_FACTORY", "mock")
else:
    print(f"FLASK PROD MODE ENABLED - GPIO SET TO HARDWARE")

from gpio_flask import flask_gpio_manager
flask_gpio_manager.debug = app.debug

@app.route("/<icao>")
def root(icao):
    metar = fetch_latest_metar(icao)
    taf = fetch_latest_taf(icao)
    return render_template("index.html", 
                           debug_info="DEBUG" if app.debug else "PROD",
                           metar=metar,
                           taf=taf)

@sock.route("/echo")
def echo(ws):
    fgm = flask_gpio_manager
    fgm.send_gpio_state(ws, app.debug)
    while True:
        data = ws.receive()
        fgm.read_client_commands(data)
        fgm.send_gpio_state(ws, app.debug)