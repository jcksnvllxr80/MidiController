# 2016
# Author: Aaron Watkins

import time
import Adafruit_GPIO as GPIO
import Adafruit_GPIO.I2C as I2C
import MCP23017_R1

class Looper_Switches(MCP23017_R1.MCP23017, object):

	LOOP_SWITCH_10             = 12
	LOOP_SWITCH_9              = 11
	LOOP_SWITCH_8              = 10
	LOOP_SWITCH_7              = 9
	LOOP_SWITCH_6              = 8

	LOOP_SWITCH_5              = 4
	LOOP_SWITCH_4              = 3
	LOOP_SWITCH_3              = 2
	LOOP_SWITCH_2              = 1
	LOOP_SWITCH_1              = 0

	SELECTOR_SWITCH            = 15
	ENCODER_CW		   		   = 6
	ENCODER_CCW                = 7

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
	footswitch_pins = [LOOP_SWITCH_1, LOOP_SWITCH_2, LOOP_SWITCH_3, LOOP_SWITCH_4, LOOP_SWITCH_5,
		LOOP_SWITCH_6, LOOP_SWITCH_7, LOOP_SWITCH_8, LOOP_SWITCH_9, LOOP_SWITCH_10]
		
	def __init__(self, address=0x22, busnum=I2C.get_default_bus()):
		# Configure MCP23017 device.
		super(Looper_Switches, self).__init__(address=address, busnum=busnum)
		self.setAllPinsInput()
		self.setAllInterruptsEnabled()
		self.inputPolarity_pin(self.SELECTOR_SWITCH, True)
		for pin in self.footswitch_pins:
			self.pullup(pin, GPIO.HIGH)
		self.readGPIO(self.allPins)        
		self.ioconSetup(0x02) #active high interrupt polarity	
		
	def setAllPinsInput(self):
		for pin in self.allPins:
			self.setup(pin, GPIO.IN)
			self.pullup(pin, True)

	def setAllInterruptsEnabled(self):
		for pin in self.allPins:
			self.gpinten_pin(pin, True)
			#	        self.intcon_pin(pin, True) # interrupt compared to defaul value 
			self.intcon_pin(pin, False) # interrupt compared to last state
			self.defval_pin(pin, True)

	def readGPIO(self, pins):
		givemeGPIO = self.input_pins(pins)
		return givemeGPIO
	
	def readGPIOBank(self, bank):
		if not bank:
			givemeGPIO = self.input_pins(self.allPins_A)
		else:
			givemeGPIO = self.input_pins(self.allPins_B)
		return givemeGPIO

	def readGPIOpin(self, pin):
		givemeGPIOpin = self.input(pin)
		return givemeGPIOpin

	def readIntrptCapByte(self, bank):
		return self.interruptCapture_byte(bank)	

	def readIntrptCapPin(self, pin):
		return self.interruptCapture(pin)

	def readIntrptFlag(self, pins):
		return self.interrupt_pins(pins)

	def readOLAT(self, pins):
		return self.outputLatch_pins(pins)

	def readOLATpin(self, pin):
		return self.outputLatch(pin)

	def enableInterruptPin(self, pin):
		self.gpinten_pin(pin, True)

	def disableInterruptPin(self, pin):
		self.gpinten_pin(pin, False)

	def enableInterrupts(self, pins):
		for pin in pins:
			self.gpinten_pin(pin, True)

	def disableInterrupts(self, pins):
		for pin in pins:
			self.gpinten_pin(pin, False) 

	def disableInterruptsByte(self, intFlagByte, bank):
		self.gpintdisable_byte(intFlagByte, bank)

	def enableInterruptsByte(self, intFlagByte, bank):
		self.gpintenable_byte(intFlagByte, bank)

	def IntrptFlagRegister(self, bank):
		return self.readIntRegister(bank)
		



