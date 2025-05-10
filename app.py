from flask import Flask, render_template
import airport_info as airports
from flask_sock import Sock


app = Flask(__name__)
app.config["TEMPLATES_AUTO_RELOAD"] = True
app.debug = True

sock = Sock()
sock.init_app(app)

@app.route("/")
def root():
    return render_template("socket_test.html")

@sock.route("/echo")
def echo(ws):
    while True:
        data = ws.receive()
        print(f"<<< {data}")
        ws.send(data)

from signal import pause
import time

# Pin Definitons:
# pwmPin = 18 # Broadcom pin 18 (P1 pin 12)
ledPin = 18
butPin = 17

from gpiozero import LED, Button
from signal import pause

led = LED(18)
button = Button(17)

button.when_pressed = led.on
button.when_released = led.off



    
