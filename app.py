from flask import Flask, render_template

import aviation_weather
import airport_info as airports

app = Flask(__name__)
app.config["TEMPLATES_AUTO_RELOAD"] = True

@app.route('/')
def root():
    return aviation_weather.fetch_latest_metar("KSFO")

# @app.route("/")
# def index():
#     return render_template("index.html")
