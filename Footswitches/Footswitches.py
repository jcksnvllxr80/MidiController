# 2016
# Author: Aaron Watkins

import Adafruit_GPIO as GPIO
import Adafruit_GPIO.I2C as I2C
import MCP23017_R1

class Looper_Switches(MCP23017_R1.MCP23017, object):

	FOOT_SWITCH_5              = 10
	FOOT_SWITCH_4              = 8
	FOOT_SWITCH_3              = 2
	FOOT_SWITCH_2              = 1
	FOOT_SWITCH_1              = 0
	SELECTOR_SWITCH            = 15

	BIT_A0	= 0
	BIT_A1	= 1
	BIT_A2	= 2
	BIT_A3	= 3
	BIT_A4	= 4
	BIT_A5	= 5
	BIT_A6	= 6
	BIT_A7	= 7
	BIT_B0  = 8
	BIT_B1  = 9
	BIT_B2  = 10
	BIT_B3  = 11
	BIT_B4  = 12
	BIT_B5  = 13
	BIT_B6  = 14
	BIT_B7  = 15
	INTPOL = 1

	allPins = [BIT_A0, BIT_A1, BIT_A2, BIT_A3, BIT_A4, BIT_A5, BIT_A6, BIT_A7, BIT_B0, BIT_B1, BIT_B2, BIT_B3, BIT_B4, BIT_B5, BIT_B6, BIT_B7]
	allPins_A = [BIT_A0, BIT_A1, BIT_A2, BIT_A3, BIT_A4, BIT_A5, BIT_A6, BIT_A7]
	allPins_B = [BIT_B0, BIT_B1, BIT_B2, BIT_B3, BIT_B4, BIT_B5, BIT_B6, BIT_B7]
	footswitch_pins = [FOOT_SWITCH_1, FOOT_SWITCH_2, FOOT_SWITCH_3, FOOT_SWITCH_4, FOOT_SWITCH_5, SELECTOR_SWITCH]
		
	def __init__(self, address=0x22, busnum=I2C.get_default_bus()):
		# Configure MCP23017 device.
		super(Looper_Switches, self).__init__(address=address, busnum=busnum)
		#self.setAllPinsInput()
		for pin in self.footswitch_pins:
			self.setup(pin, GPIO.IN)
			self.pullup(pin, GPIO.HIGH)
		for pin in self.footswitch_pins:
			self.gpinten_pin(pin, True)
			self.intcon_pin(pin, False) # interrupt compared to last state
			self.defval_pin(pin, True)
		self.inputPolarity_pin(self.SELECTOR_SWITCH, True)
		self.pullup(self.SELECTOR_SWITCH, False)
		
		self.readGPIO(self.allPins)        
		self.ioconSetup(0x02) #active high interrupt polarity	

	def readGPIO(self, pins):
		givemeGPIO = self.input_pins(pins)
		return givemeGPIO

	def readIntrptCapPin(self, pin):
		return self.interruptCapture(pin)

	def enableInterruptPin(self, pin):
		self.gpinten_pin(pin, True)

	def disableInterruptPin(self, pin):
		self.gpinten_pin(pin, False)

	def IntrptFlagRegister(self, bank):
		return self.readIntRegister(bank)
		



