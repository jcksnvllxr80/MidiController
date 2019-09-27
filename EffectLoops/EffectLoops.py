# 2016
# Author: Aaron Watkins

import time
import MIDI
import Routes
import LEDs
import RPi.GPIO as GPIO
import logging

'''   ############ USAGE ###############
logger.info("info message")
logger.warning("warning message")
logger.error("error message")
'''
logger = logging.getLogger(__name__)   
logger.setLevel(logging.DEBUG)
logger.propagate = False
# create console handler and set level to info
handler = logging.StreamHandler()
handler.setLevel(logging.INFO)
formatter = logging.Formatter("%(asctime)s [EffectLoops.py] [%(levelname)-5.5s]  %(message)s")
handler.setFormatter(formatter)
logger.addHandler(handler)

Routing = Routes.Looper_Routes()
Leds = LEDs.Looper_LEDs()

def unload():
	Leds.stop_pwm()

class Pedal(object):

	def __init__(self, name, state, type):
		self.name = name
		self.type = type
		self.is_engaged = state
		if self.is_engaged:
			self.turn_on()
		else:
			self.turn_off()	
	
	def __str__(self):
		return self.name + " " + self.getState()
	
	def getState(self):
		if self.is_engaged:
			return "Engaged"
		else:
			return "Bypassed"
			
			
class MidiPedal(object):
	
	def __init__(self, MIDIchannel):
		self.midi = MIDI.MIDI(MIDIchannel)
		self.MIDIchannel = MIDIchannel

	
#class ButtonOnPedalBoard(Pedal, ButtonDisplay):
class ButtonOnPedalBoard(Pedal):

	FUNC_1 = 6
	FUNC_2 = 7
	FUNC_3 = 13
	FUNC_4 = 14

	def __init__(self, name, state, button, type, func_two_type, func_two_port, **kwargs):
		self.button = button
		self.start = time.time()
		self.pin = self.from_button_to_pin(self.button)
		self.func_two_port = func_two_port
		self.func_two_type = func_two_type
		self.is_pressed = False
		self.partner = None
		self.last_action_time = time.time()
		self.PedalConfigChanged = False
		super(ButtonOnPedalBoard, self).__init__(name, state, type)

			
	def from_button_to_pin(self, button):
		if button < 6:
			return button - 1
		elif button < 11:
			return button + 2
		else:
			return button

	def set_partner(self, partner):
		self.partner = partner

	def get_partner_button(self):
		if self.button < 6:
			return self.button + 5
		elif self.button < 11:
			return self.button - 5

	def secondaryFunction(self):
		portPin = self.getPortPin()
		if self.func_two_type == "Momentary":
			Routing.changeOutputPinState(portPin)
			time.sleep(0.1)
			Routing.changeOutputPinState(portPin)
		elif self.func_two_type == "Latching":
			Routing.changeOutputPinState(portPin)
		elif self.func_two_type == "Settings":
			logger.info("Settings")
		else:	
			logger.info("None " + str(self.button))
			

	def getPortPin(self):
		func_dict = {
			"FUNC_1": self.FUNC_1, 
			"FUNC_2": self.FUNC_2,
			"FUNC_3": self.FUNC_3, 
			"FUNC_4": self.FUNC_4
		}
		return func_dict.get(self.func_two_port, None)


	def setSecondaryFunction(self, func_two_type, func_two_port):
		self.func_two_port = func_two_port
		self.func_two_type = func_two_type

	def turn_on(self):
		Routing.set_output(self.pin, False)
		Leds.set_output(self.pin, False)
		self.is_engaged = True
		logger.info(self)

	def turn_off(self):
		if self.name <> "Empty":
			Routing.set_output(self.pin, True)
			Leds.set_output(self.pin, True)
			self.is_engaged = False
	  else:
			Leds.set_output(self.pin, False)
			self.is_engaged = True
		logger.info(self)
	
	def getPin(self):
		return self.pin
		
	def set_setting(self, setting):
		pass
		logger.info("setting " + str(setting))

	def get_partner_function(self):
		if self.pin > 5:
			return self.partner.button
		else:
			return self.button
			

class TapTempoButton(ButtonOnPedalBoard):

	MIDITempoPedal = None
	#GPIO pin on rpi
	TAP_PIN1 = 5
	TAP_PIN2 = 6
	TAP_PIN3 = 26
	TAP_PIN4 = 27

	def __init__(self, name, button, tempo, midiTempoPed):
		self.MIDITempoPedal = midiTempoPed
		type = "TapTempoButton"
		state = True
		func_two_type = "None"
		func_two_port = "None"
		super(TapTempoButton, self).__init__(name, state, button, type, func_two_type, func_two_port)
		self.lastTap = time.time() - 2.5 #because the last tap being more than 2.5s ago means "start over"
		self.avgTapTime = 0 #only to start with
		self.TapNum = 0
		self.pwm_on_time = 0
		self.tap_start_time = 0
		self.tapping_in_progress = False
		self.init_pwm(tempo) #initalize GPIO for PWM
		#self.setTempo(tempo)

	def setTempo(self, tempo):
		if tempo > 99.9:
			self.tempo = int(tempo)
		else:
			self.tempo = tempo
		self.start_pwm(self.tempo/60) #start the PWM with BPM/60 so BPS
		self.pwm_on_time = 4*60/self.tempo #4 beats

	def init_pwm(self,tempo):
		#set the mode for how the GPIO pins will be numbered
		GPIO.setmode(GPIO.BCM)
		#set the list of pin numbers as outputs
		GPIO.setup([self.TAP_PIN1, self.TAP_PIN2, self.TAP_PIN3, self.TAP_PIN4], GPIO.OUT)
		#set freq and pin number to a PWM object for each of the 3 RGB components
		self._tap1 = GPIO.PWM(self.TAP_PIN1, tempo/60)
		self._tap2 = GPIO.PWM(self.TAP_PIN2, tempo/60)
		self._tap3 = GPIO.PWM(self.TAP_PIN3, tempo/60)
		self._tap4 = GPIO.PWM(self.TAP_PIN4, tempo/60)
		self.DC1 = 75
		self.DC2 = 75
		self.DC3 = 75
		self.DC4 = 75

	def start_pwm(self, tempoBPS):
		'''start PWM with beats per second frequency and (100 - x) dutyCycle
		'''
		self._tap1.ChangeFrequency(tempoBPS)
		self._tap2.ChangeFrequency(tempoBPS)
		self._tap3.ChangeFrequency(tempoBPS)
		self._tap4.ChangeFrequency(tempoBPS)
		#GPIO.output(self.TAP_PIN1, 0)
		self._tap1.start(100 - self.DC1)
		#GPIO.output(self.TAP_PIN2, 0)
		self._tap2.start(100 - self.DC2)
		#GPIO.output(self.TAP_PIN3, 0)
		self._tap3.start(100 - self.DC3)
		#GPIO.output(self.TAP_PIN4, 0)
		self._tap4.start(100 - self.DC4)
		self.tap_start_time = time.time()
		self.tapping_in_progress = True

	def pause_pwm(self):
		'''pause the PWM
		'''
		self._tap1.stop()
		#GPIO.output(self.TAP_PIN1, 1)
		self._tap2.stop()
		#GPIO.output(self.TAP_PIN2, 1)
		self._tap3.stop()
		#GPIO.output(self.TAP_PIN3, 1)
		self._tap4.stop()
		#GPIO.output(self.TAP_PIN4, 1)
		self.tapping_in_progress = False

	def stop_pwm(self):
		'''stop the PWM
		'''
		self.pause_pwm()
		GPIO.cleanup()

	def turn_on(self):
		Leds.set_output(self.pin, False)
		self.is_engaged = True
		logger.info(self)

	def turn_off(self):
		Leds.set_output(self.pin, True)
		self.is_engaged = False
		logger.info(self)
		
	def setDutyCycle1(self, DC):
		self.DC1 = DC

	def setDutyCycle2(self, DC):
		self.DC2 = DC

	def setDutyCycle3(self, DC):
		self.DC3 = DC

	def setDutyCycle4(self, DC):
		self.DC4 = DC

	def getDutyCycle1(self):
		return self.DC1

	def getDutyCycle2(self):
		return self.DC2

	def getDutyCycle3(self):
		return self.DC3

	def getDutyCycle4(self):
		return self.DC4

	def getTempo(self):
		return self.tempo

	def button_state(self, int_capture_pin_val, mode):
		if not int_capture_pin_val:
			self.turn_off()
			self.MIDITempoPedal.tapTempo()
			self.is_pressed = True
			self.start = time.time()
			self.calculate_tempo()
		else:
			self.turn_on()
			if self.TapNum > 4:
				time.sleep(self.avgTapTime)
				self.setTempo(int(10 * (60 / self.avgTapTime)) / 10.0 )
				if self.MIDITempoPedal is not None:
					self.MIDITempoPedal.setTempo(self.tempo)
			self.is_pressed = False

	def calculate_tempo(self):
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

	def __init__(self, name, button, state, func_two_type, func_two_port):
		type = "LoopPedal"
		super(LoopPedal, self).__init__(name, state, button, type, func_two_type, func_two_port)

	def button_state(self, int_capture_pin_val, mode):
		if not int_capture_pin_val:
			self.is_pressed = True
			self.start = time.time()
		else:
			self.end = time.time()
			delta_t = self.end - self.start
			if not self.partner.PedalConfigChanged:
				if time.time() - self.partner.last_action_time > 0.25:
					if mode == "Pedal":
						if not self.is_engaged:
							self.turn_on()
						else:
							if delta_t < 0.5:
								self.turn_off()
							else:
								self.secondaryFunction()
					else:
						if delta_t > 0.5:
							if not self.is_engaged:
								self.turn_on()
							else:
								self.turn_off()
			else:
				#self.PedalConfigChanged == False
				self.partner.PedalConfigChanged = False
			self.is_pressed = False


class MidiLoopPedal(LoopPedal, MidiPedal):

	SelahCommands = {"DATA_BYTE":"\x0F", "TS808_CLIP_CC":"\x50", "PLEXI_CLIP_CC":"\x51", 
		"KLONE_CLIP_CC":"\x52", "ENGAGE_CC":"\x64", "BYPASS_CC":"\x65", "CYCLE_CLIP_CC":"\x5D", 
		"TOGGLEBYPASS_CC":"\x67"}

	def __init__(self, name, pin, state, preset, MIDIchannel, func_two_type, func_two_port, brand):
		self.type = "MidiLoopPedal"
		self.brand = brand
		self.preset = preset
		MidiPedal.__init__(self, MIDIchannel) 
		if self.brand == "Selah":
			self.MidiCommandDict = self.SelahCommands
			self.setSelahPreset(self.preset)
		LoopPedal.__init__(self, name, pin, state, func_two_type, func_two_port)

	def turn_on(self):
		#turn on via MIDI
		# self.midi.MIDI_CC_TX(self.MidiCommandDict["ENGAGE_CC"], self.MidiCommandDict["DATA_BYTE"])
		LoopPedal.turn_on(self)
		# logger.info(self.name + " on.")

	def turn_off(self):
		#turn off via MIDI
		# self.midi.MIDI_CC_TX(self.MidiCommandDict["BYPASS_CC"], self.MidiCommandDict["DATA_BYTE"])
		LoopPedal.turn_off(self)
		# logger.info(self.name + " off.")

	def setSelahPreset(self, preset):
		self.preset = preset
		if preset == "Plexi":
			self.midi.SelahPresetChange(self.MidiCommandDict["PLEXI_CLIP_CC"], self.MidiCommandDict["DATA_BYTE"])		
		if preset == "TS808":
			self.midi.SelahPresetChange(self.MidiCommandDict["TS808_CLIP_CC"], self.MidiCommandDict["DATA_BYTE"])		
		if preset == "Klone":
			self.midi.SelahPresetChange(self.MidiCommandDict["KLONE_CLIP_CC"], self.MidiCommandDict["DATA_BYTE"])		

	def secondaryFunction(self):
		if self.func_two_type == "MIDI":
			self.midi.MIDI_CC_TX(self.MidiCommandDict[self.func_two_port], self.MidiCommandDict["DATA_BYTE"])
		else:
			super(MidiLoopPedal, self).secondaryFunction()
	
	def set_setting(self, setting):
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

	def turn_on(self):
		if not self.brand == "Selah":
			#turn on via MIDI
			self.midi.MIDI_CC_TX(self.MidiCommandDict["ENGAGE_CC"], self.MidiCommandDict["DATA_BYTE_ON"])
			self.is_engaged = True
			logger.info(self.name + " on.")

	def turn_off(self):
		if not self.brand == "Selah":
			#turn off via MIDI
			self.midi.MIDI_CC_TX(self.MidiCommandDict["BYPASS_CC"], self.MidiCommandDict["DATA_BYTE_OFF"])
			self.is_engaged = False
			logger.info(self.name + " off.")

	def setStrymonPreset(self, preset):
		self.preset = preset
		presetGroup = preset / 128
		preset = preset % 128
		self.midi.StrymonPresetChange(self.MidiCommandDict["PRESET_GROUP_" + str(presetGroup)], chr(preset))

	def setSelahPreset(self, preset):
		self.preset = preset
		self.midi.SelahPresetTempoChange(chr(preset))
	    	
	def set_setting(self, setting):
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
		func_two_type = "None"
		func_two_port = "None"
		super(Empty, self).__init__(name, state, button, type, func_two_type, func_two_port)

	def button_state(self, int_capture_pin_val, mode):
		
		if not int_capture_pin_val:
			self.turn_on()
			self.is_pressed = True
		else:
			self.turn_off()
			self.is_pressed = False
			