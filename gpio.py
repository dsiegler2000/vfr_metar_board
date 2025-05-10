# import RPi.GPIO as GPIO
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

# try:
#     x = 1
#     while True:
#         if x == 1:
#             print("hi")
#             led.on
#             x = 0
#         else:
#             led.off
#             x = 1
#         time.sleep(1)
# except KeyboardInterrupt: # If CTRL+C is pressed, exit cleanly:
#     # pwm.stop() # stop PWM
#     GPIO.cleanup() # cleanup all GPIO

pause()


# try:
#     def f(n):
#         print("Button pressed!")

#     GPIO.add_event_detect(butPin, GPIO.FALLING, f, bouncetime=300)
#     pause()
# except KeyboardInterrupt:
#     GPIO.cleanup()
#     raise SystemExit


# print("Here we go! Press CTRL+C to exit")
# try:
#     while 1:
#         if GPIO.input(butPin): # button is released
#             # pwm.ChangeDutyCycle(dc)
#             GPIO.output(ledPin, GPIO.LOW)
#         else: # button is pressed:
#             # pwm.ChangeDutyCycle(100-dc)
#             GPIO.output(ledPin, GPIO.HIGH)
#             time.sleep(0.075)
#             GPIO.output(ledPin, GPIO.LOW)
#             time.sleep(0.075)
# except KeyboardInterrupt: # If CTRL+C is pressed, exit cleanly:
#     # pwm.stop() # stop PWM
#     GPIO.cleanup() # cleanup all GPIO