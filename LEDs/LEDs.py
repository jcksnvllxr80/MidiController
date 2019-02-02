# 2016
# Author: Aaron Watkins

import time
import Adafruit_GPIO as GPIO
import RPi.GPIO as piGPIO
import Adafruit_GPIO.I2C as I2C
import MCP23017_R1

class Looper_LEDs(MCP23017_R1.MCP23017, object):
	"""Class to represent each pedals on or off state with an LED
	"""

	#global variables
	PWM_PIN = 13
	PWM_PIN_FREQ = 1000

	LOOP_LED_10     = 10
	LOOP_LED_9      = 9
	LOOP_LED_8      = 8
	LOOP_LED_7      = 7
	LOOP_LED_6      = 6
	LOOP_LED_5      = 5
	LOOP_LED_4      = 4
	LOOP_LED_3      = 3
	LOOP_LED_2      = 2
	LOOP_LED_1      = 1
	LOOP_LED_0      = 0 
	MODE_PLAY_LIVE  = 14

	BIT_A0  = 0
	BIT_A1  = 1
	BIT_A2  = 2
	BIT_A3  = 3
	BIT_A4  = 4
	BIT_A5  = 5
	BIT_A6  = 6
	BIT_A7  = 7
	BIT_B0  = 8
	BIT_B1  = 9
	BIT_B2  = 10
	BIT_B3  = 11
	BIT_B4  = 12
	BIT_B5  = 13
	BIT_B6  = 14
	BIT_B7  = 15

	allPins = [BIT_A0, BIT_A1, BIT_A2, BIT_A3, BIT_A4, BIT_A5, BIT_A6, BIT_A7, BIT_B0, BIT_B1, 
		BIT_B2, BIT_B3, BIT_B4, BIT_B5, BIT_B6, BIT_B7]

	def __init__(self, address=0x23, busnum=I2C.get_default_bus()):
		"""Initialize the LEDs
		"""
		# Configure MCP23017 device.
		super(Looper_LEDs, self).__init__(address=address, busnum=busnum)
		self.setAllPinsOutput()
		self.initPWM() #initalize GPIO for PWM
	
	def initPWM(self):
		#set the mode for how the GPIO pins will be numbered
		piGPIO.setmode(piGPIO.BCM)
		#set the list of pin numbers as outputs
		piGPIO.setup(self.PWM_PIN, piGPIO.OUT)
		#set freq and pin number to a PWM object
		self._pwm = piGPIO.PWM(self.PWM_PIN, self.PWM_PIN_FREQ).start(50)

	def setAllPinsOutput(self):
		for pin in self.allPins:
			self.setup(pin, GPIO.OUT)

	def changeOutputPinState(self, pin):
		self.output(pin, True ^ self.input(pin)) #xor value with input and assign to output for that pin
		return self.input(pin)

	def set_output(self, pin, value):
		self.output(pin, value)

