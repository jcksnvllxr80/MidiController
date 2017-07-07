# 2016
# Author: Aaron Watkins

import time
import MIDI
import Routes
import LEDs
import Adafruit_GPIO.SPI as SPI
import SSD1306
import RPi.GPIO as GPIO
import SlaveSelect

from PIL import Image
from PIL import ImageFont
from PIL import ImageDraw

RST = 25
DC = 12
SPI_PORT = 0
SPI_DEVICE = 0
FONT_FOLDER = '/home/pi/Looper/test/Font/'

slave_select = SlaveSelect.SlaveSelect()
spi_disp = SSD1306.SSD1306_128_64(rst=RST, dc=DC, spi=SPI.SpiDev(SPI_PORT, SPI_DEVICE, max_speed_hz=8000000))
Routing = Routes.Looper_Routes()
Leds = LEDs.Looper_LEDs()

class Pedal(object):
    
	def __init__(self, name, state, type):
		self.name = name
		self.type = type
		self.isEngaged = state
		if self.isEngaged:
			self.turnOn()
		else:
			self.turnOff()	
	
	def __str__(self):
		return self.name + " " + self.getState()
	
	def getState(self):
		if self.isEngaged:
			return "Engaged"
		else:
			return "Bypassed"


class ButtonDisplay(object):

	font_type = None
	font_size = 0
	currentButton_SongMode = None

	def __init__(self, ft=None, fs=None):	
		if ft is None and fs is None:
			self.invertDisplayColors = False
			self.spiEnable()
			spi_disp.begin()
			self.width = spi_disp.width
			self.height = spi_disp.height
			spi_disp.clear()
			spi_disp.display()
			self.spiDisable()
		else:
			ButtonDisplay.font_type = ft
			ButtonDisplay.font_size = fs
			
			
	def setButtonDisplayMessage(self, msg, mode):
		self.message = msg
		backgroundColor = 0
		textColor = 255
		image = Image.new('1', (self.width, self.height))
		font = ImageFont.truetype(FONT_FOLDER + self.font_type + ".ttf", self.font_size)
		draw = ImageDraw.Draw(image)
		# Clear image buffer by drawing a black filled box.
		if self.invertDisplayColors and mode == "Song":
			backgroundColor = 255
			textColor = 0
		draw.rectangle((0,0,self.width,self.height), outline=backgroundColor, fill=backgroundColor)

		for str in msg.split():
			xMax, yMax = draw.textsize(str, font=font)
			x = (self.width - xMax)/2
			y = 0
			draw.text((x, y), str, font=font, fill=textColor) 
			y += yMax + 2	
			
		self.spiEnable()
		spi_disp.image(image)
		spi_disp.display()
		self.spiDisable()
	
	def setFont(self, fontType=None, fontSize=None):
		if fontType is not None:
			ButtonDisplay.font_type = fontType
		if fontSize is not None:
			ButtonDisplay.font_size = int(fontSize)	
		
	def spiEnable(self):	
		slave_select.set_output(self.button,GPIO.LOW)
	
	def spiDisable(self):
		slave_select.set_output(self.button,GPIO.HIGH)
			
			
class MidiPedal(object):
	
	def __init__(self, MIDIchannel):
		self.midi = MIDI.MIDI(MIDIchannel)
		self.MIDIchannel = MIDIchannel

	
class ButtonOnPedalBoard(Pedal, ButtonDisplay):

	EXP_TIP_1 = 6
	TAP_RING_2 = 7

	def __init__(self, name, state, button, type, FuncTwoType, FuncTwoPort, **kwargs):
		self.button = button
		self.start = time.time()
		self.pin = self.fromButtonToPin(self.button)
		self.FuncTwoPort = FuncTwoPort
		self.FuncTwoType = FuncTwoType
		self.isPressed = False
		self.partner = None
		self.lastActionTime = time.time()
		self.PedalConfigChanged = False
		super(ButtonOnPedalBoard, self).__init__(name, state, type)
		if name == "RotaryPB":
			ButtonDisplay.__init__(self, **kwargs)
		else:
			ButtonDisplay.__init__(self)

			
	def fromButtonToPin(self, button):
		if button < 6:
			return button - 1
		elif button < 11:
			return button + 2
		else:
			return button

	def setPartner(self, partner):
		self.partner = partner

	def getPartnerButton(self):
		if self.button < 6:
			return self.button + 5
		elif self.button < 11:
			return self.button - 5

	def secondaryFunction(self):
		portPin = self.getPortPin()
		if self.FuncTwoType == "Momentary":
			Routing.changeOutputPinState(portPin)
			time.sleep(0.1)
			Routing.changeOutputPinState(portPin)
		elif self.FuncTwoType == "Latching":
			Routing.changeOutputPinState(portPin)
		elif self.FuncTwoType == "Settings":
			print "Settings"
		else:	
			print "None " + str(self.button)
			

	def getPortPin(self):
		if self.FuncTwoPort == "EXP_TIP_1":
			return self.EXP_TIP_1
		elif self.FuncTwoPort == "TAP_RING_2":
			return self.TAP_RING_2

	def setSecondaryFunction(self, FuncTwoType, FuncTwoPort):
		self.FuncTwoPort = FuncTwoPort
		self.FuncTwoType = FuncTwoType

	def turnOn(self):
		Routing.set_output(self.pin, False)
		Leds.set_output(self.pin, True)
		self.isEngaged = True
		#print self

	def turnOff(self):
		if self.name <> "Empty":
			Routing.set_output(self.pin, True)
		Leds.set_output(self.pin, False)
		self.isEngaged = False
		#print self
	
	def getPin(self):
		return self.pin
		
	def setSetting(self, setting):
		pass
		#print "setting " + str(setting)

	def getPartnerFunction(self):
		if self.pin > 5:
			return self.partner.button
		else:
			return self.button
			

class TapTempoButton(ButtonOnPedalBoard):
    
    MIDITempoPedal = None
 
    def __init__(self, name, button, tempo, midiTempoPed):
	self.MIDITempoPedal = midiTempoPed
	type = "TapTempoButton"
	state = True
	FuncTwoType = "None"
	FuncTwoPort = "None"
	super(TapTempoButton, self).__init__(name, state, button, type, FuncTwoType, FuncTwoPort)
	self.lastTap = time.time() - 2.5 #because the last tap being more than 2.5s ago means "start over"
	self.avgTapTime = 0 #only to start with
	self.TapNum = 0
	#self.setTempo(tempo)

    def setTempo(self, tempo):
	if tempo > 99.9:
	    self.tempo = int(tempo)
	else:
            self.tempo = tempo
	sleepTime = 60.0/self.tempo #seconds/beat
        for num in range(4):
	    self.start = time.time()
	    self.turnOff()
	    time.sleep(0.05)
	    self.turnOn()
	    time.sleep(sleepTime - (time.time() - self.start)) 

    def getTempo(self):
	return self.tempo	

    def buttonState(self, intCapturePinVal):
        if not intCapturePinVal:
	    self.turnOff()
	    self.MIDITempoPedal.tapTempo()
            self.isPressed = True
	    self.start = time.time()
	    self.calculateTempo()
        else:
	    self.turnOn()
   	    if self.TapNum > 4:
		time.sleep(self.avgTapTime)
		self.setTempo(int(10 * (60 / self.avgTapTime)) / 10.0 )	    
		if self.MIDITempoPedal is not None:
		    self.MIDITempoPedal.setTempo(self.tempo)
            self.isPressed = False

    def calculateTempo(self):
	if (time.time() - self.lastTap) > 2.5: #no need to go less than 24 BPM
	    self.TapNum = 0
	elif self.TapNum == 1:
	    self.TapTime1 = time.time() - self.lastTap
	elif self.TapNum == 2:
            self.TapTime2 = time.time() - self.lastTap
	elif self.TapNum == 3:
            self.TapTime3 = time.time() - self.lastTap
	else:
	    self.TapTime1 = self.TapTime2
	    self.TapTime2 = self.TapTime3
	    self.TapTime3 = time.time() - self.lastTap
	    self.avgTapTime = (self.TapTime1 + self.TapTime2 + self.TapTime3) / 3.0	    	
	self.TapNum += 1    
	self.lastTap = time.time()


class LoopPedal(ButtonOnPedalBoard):

    def __init__(self, name, button, state, FuncTwoType, FuncTwoPort):
	type = "LoopPedal"
	super(LoopPedal, self).__init__(name, state, button, type, FuncTwoType, FuncTwoPort)
	    	
    def buttonState(self, intCapturePinVal, mode):
		if not intCapturePinVal:
			self.isPressed = True
			self.start = time.time()
		else:
			self.end = time.time()
			deltaT = self.end - self.start
			if not self.partner.PedalConfigChanged:
				if time.time() - self.partner.lastActionTime > 0.25:
					if mode == "Pedal":
						if not self.isEngaged:
							self.turnOn()
						else:
							if deltaT < 0.5:
								self.turnOff()
							else:
								self.secondaryFunction()
					else:
						if deltaT < 0.5:
							#ButtonDisplay.currentButton_SongMode.invertDisplayColors = False
							#ButtonDisplay.currentButton_SongMode = self
							#self.invertDisplayColors = True
							pass
						else:
							if not self.isEngaged:
								self.turnOn()
							else:
								self.turnOff()
			else:
				#self.PedalConfigChanged == False
				self.partner.PedalConfigChanged == False
			self.isPressed = False


class MidiLoopPedal(LoopPedal, MidiPedal):

	SelahCommands = {"DATA_BYTE":"\x0F", "TS808_CLIP_CC":"\x50", "PLEXI_CLIP_CC":"\x51", 
		"KLONE_CLIP_CC":"\x52", "ENGAGE_CC":"\x64", "BYPASS_CC":"\x65", "CYCLE_CLIP_CC":"\x5D", 
		"TOGGLEBYPASS_CC":"\x67"}

	def __init__(self, name, pin, state, preset, MIDIchannel, FuncTwoType, FuncTwoPort, brand):
		self.type = "MidiLoopPedal"
		self.brand = brand
		self.preset = preset
		MidiPedal.__init__(self, MIDIchannel) 
		if self.brand == "Selah":
			self.MidiCommandDict = self.SelahCommands
			self.setSelahPreset(self.preset)
		LoopPedal.__init__(self, name, pin, state, FuncTwoType, FuncTwoPort)

	def turnOn(self):
		#turn on via MIDI
		self.midi.MIDI_CC_TX(self.MidiCommandDict["ENGAGE_CC"], self.MidiCommandDict["DATA_BYTE"])
		LoopPedal.turnOn(self)
		#print self.name + " on."

	def turnOff(self):
		#turn off via MIDI
		self.midi.MIDI_CC_TX(self.MidiCommandDict["BYPASS_CC"], self.MidiCommandDict["DATA_BYTE"])
		LoopPedal.turnOff(self)
		#print self.name + " off."

	def setSelahPreset(self, preset):
		self.preset = preset
		if preset == "Plexi":
			self.midi.SelahPresetChange(self.MidiCommandDict["PLEXI_CLIP_CC"], self.MidiCommandDict["DATA_BYTE"])		
		if preset == "TS808":
			self.midi.SelahPresetChange(self.MidiCommandDict["TS808_CLIP_CC"], self.MidiCommandDict["DATA_BYTE"])		
		if preset == "Klone":
			self.midi.SelahPresetChange(self.MidiCommandDict["KLONE_CLIP_CC"], self.MidiCommandDict["DATA_BYTE"])		

	def secondaryFunction(self):
		if self.FuncTwoType == "MIDI":
			self.midi.MIDI_CC_TX(self.MidiCommandDict[self.FuncTwoPort], self.MidiCommandDict["DATA_BYTE"])
		else:
			super(MidiLoopPedal, self).secondaryFunction()
	
	def setSetting(self, setting):
		if self.brand == "Selah":
			self.setSelahPreset(setting)


class MidiNonLoopPedal(MidiPedal, Pedal):
	#Strymon Pedals are the only Pedals not routed through the looper
	StrymonCommands = {"DATA_BYTE_ON":"\x7F", "DATA_BYTE_OFF":"\x00", "DATA_BYTE":"\x0F", 
		"PRESET_GROUP_0":"\x00\x00", "PRESET_GROUP_1":"\x00\x01", "PRESET_GROUP_2":"\x00\x02", 
		"ENGAGE_CC":"\x66", "BYPASS_CC":"\x66", "TAP_CC":"\x5D", "TOGGLEBYPASS_CC":"\x1D"}
	SelahCommands = {}

	def __init__(self, name, state, MIDIchannel, brand, preset):
		type = "MidiNonLoopPedal"
		self.brand = brand
		MidiPedal.__init__(self, MIDIchannel)
		self.preset = preset
		if self.brand == "Strymon":
			self.MidiCommandDict = self.StrymonCommands
			self.setStrymonPreset(self.preset)
		elif self.brand == "Selah":
			self.MidiCommandDict = self.SelahCommands
			self.setSelahPreset(self.preset)
		Pedal.__init__(self, name, state, type) 

	def turnOn(self):
		if not self.brand == "Selah":
			#turn on via MIDI
			self.midi.MIDI_CC_TX(self.MidiCommandDict["ENGAGE_CC"], self.MidiCommandDict["DATA_BYTE_ON"])
			self.isEngaged = True
			#print self.name + " on."

	def turnOff(self):
		if not self.brand == "Selah":
			#turn off via MIDI
			self.midi.MIDI_CC_TX(self.MidiCommandDict["BYPASS_CC"], self.MidiCommandDict["DATA_BYTE_OFF"])
			self.isEngaged = False
			#print self.name + " off."

	def setStrymonPreset(self, preset):
		self.preset = preset
		presetGroup = preset / 128
		preset = preset % 128
		self.midi.StrymonPresetChange(self.MidiCommandDict["PRESET_GROUP_" + str(presetGroup)], chr(preset))

	def setSelahPreset(self, preset):
		self.preset = preset
		self.midi.SelahPresetTempoChange(chr(preset))
	    	
	def setSetting(self, setting):
		if self.brand == "Strymon":
			self.setStrymonPreset(int(setting))
		elif self.brand == "Selah":
			self.setSelahPreset(int(setting))
		

class TimeLine(MidiNonLoopPedal):
    
	TimeLineSysExTempoStart = "\xF0\x00\x01\x55\x12\x01\x6F\x00\x00\x00" 
	TimeLineSysExEnd= "\xF7"

	def __init__(self, name, state, MIDIchannel, brand, tempo, preset):
		self.type = "TimeLine"
		self.tempo = tempo
		super(TimeLine, self).__init__(name, state, MIDIchannel, brand, preset)
		self.setTempo(self.tempo)

	def setTempo(self, tempo):
		#set tempo via MIDI
		self.delayInMs = int(60000/tempo)
		self.midi.SysEx_TX(self.TimeLineSysExTempoStart + chr(self.delayInMs//128) + chr(self.delayInMs%128) 
			+ self.TimeLineSysExEnd)

	def tapTempo(self):
		self.midi.MIDI_CC_TX(self.MidiCommandDict["TAP_CC"], self.MidiCommandDict["DATA_BYTE"])


class Empty(ButtonOnPedalBoard):

	def __init__(self, name, button, state):
		type = "Empty"
		FuncTwoType = "None"
		FuncTwoPort = "None"
		super(Empty, self).__init__(name, state, button, type, FuncTwoType, FuncTwoPort)

	def buttonState(self, intCapturePinVal, mode):
		
		if not intCapturePinVal:
			self.turnOn()
			self.isPressed = True
		else:
			#if mode == "Song":
				#ButtonDisplay.currentButton_SongMode.invertDisplayColors = False
				#ButtonDisplay.currentButton_SongMode = self
				#self.invertDisplayColors = True
			self.turnOff()
			self.isPressed = False
			



