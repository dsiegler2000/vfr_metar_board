"""Helper functions to manage GPIO state & transmit via socket"""

from gpiozero import LED, Button
from config import config
import json
import time

class FlaskGPIOManager:
    # TODO implement fully no code configurable manager
    # should include support for arbitrary variables that aren't GPIO (live state)
    def __init__(self):
        self.button = Button(config["button_gpio_pin"])
        self.led = LED(config["led_gpio_pin"])

        # Configure button callback
        self.button.when_pressed = self.on_button_pressed

        self._gpio_state = {
            "button": False,
            "led": True
        }

    def on_button_pressed(self):
        self._gpio_state["button"] = True

    def send_gpio_state(self, ws, debug):
        self._gpio_state["time"] = time.time()
        ws.send(self._gpio_state)
        self._gpio_state["button"] = False

    def read_client_commands(self, client_commands):
        c = json.loads(client_commands)
        if c["led"]:
            self.led.on()
        else:
            self.led.off()
        self._gpio_state["led"] = c["led"]

flask_gpio_manager = FlaskGPIOManager()