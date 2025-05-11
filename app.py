import os
import time

from flask import Flask, render_template, send_from_directory, send_file
# from flask_sock import Sock

# import airport_info as airports
# from aviation_weather import fetch_latest_metar, fetch_latest_taf
# from render import render_metar

app = Flask(__name__)

# sock = Sock()
# sock.init_app(app)

if app.debug:
    print(f"FLASK DEBUG MODE ENABLED - GPIO SET TO MOCK")
    # os.environ["GPIOZERO_PIN_FACTORY"] = os.environ.get("GPIOZERO_PIN_FACTORY", "mock")
else:
    print(f"FLASK PROD MODE ENABLED - GPIO SET TO HARDWARE")

# from gpio_flask import flask_gpio_manager
# flask_gpio_manager.debug = app.debug

# TEST_ICAOS = [
#     "ksfo",
#     "ksck",
#     "ksql",
#     "sfo",
#     "sck",
#     "sql"
# ]
# for a in TEST_ICAOS:
#     print(f"http://127.0.0.1:5000/testing/{a}")

# @app.route("/testing/<icao>")
# def testing_icao(icao):
#     print("a")
#     metar = fetch_latest_metar(icao)
#     taf = fetch_latest_taf(icao)
#     t = int(time.time())
#     return render_template("index.html", 
#                            debug_info="DEBUG" if app.debug else "PROD",
#                            metar=metar,
#                            taf=taf)

# @app.route("/image_testing")
# def get_image():
#     return send_file(render_metar(fetch_latest_metar("KOAK")), mimetype="image/png")

# @app.route("/favicon.ico")
# def favicon():
#     return send_from_directory(os.path.join(app.root_path, "static"), "favicon.ico", mimetype="image/vnd.microsoft.icon")

@app.route("/")
def root():
    print("hit!")
    return "Hi"

# @sock.route("/echo")
# def echo(ws):
#     fgm = flask_gpio_manager
#     fgm.send_gpio_state(ws, app.debug)
#     while True:
#         data = ws.receive()
#         fgm.read_client_commands(data)
#         fgm.send_gpio_state(ws, app.debug)