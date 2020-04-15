# 2016
# Author: Aaron Watkins

import time
import MIDI
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


def unload():
	pass

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


class ButtonOnPedalBoard(object):

	def __init__(self, name, button, **kwargs):
		self.name = name
		self.button = button
		self.start = time.time()
		self.pin = self.from_button_to_pin(self.button)
		self.is_pressed = False
		self.partner = None
		self.last_action_time = self.start
		self.PedalConfigChanged = False


	def button_state(self, int_capture_pin_val, mode):
		output = None
		if not int_capture_pin_val:
			self.is_pressed = True
			self.start = time.time()
		else:
			self.end = time.time()
			delta_t = self.end - self.start
			if not self.partner.PedalConfigChanged:
				if time.time() - self.partner.last_action_time > 0.25:
					# if mode == "favorite":
					# 	self.secondaryFunction()
					# else:
					if delta_t > 0.5:
						output = self.name
			else:
				output = "partner func"
				self.partner.PedalConfigChanged = False
			self.is_pressed = False
		return output


	def from_button_to_pin(self, button):
		if button:
			if button < 6:
				return button - 1
			elif button < 11:
				return button + 2
			else:
				return button
		else:
			return None


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
			# Routing.changeOutputPinState(portPin)
			time.sleep(0.1)
			# Routing.changeOutputPinState(portPin)
		elif self.func_two_type == "Latching":
			pass
			# Routing.changeOutputPinState(portPin)
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
		self.is_engaged = True
		logger.info(self)


	def turn_off(self):
		if self.name <> "Empty":
			self.is_engaged = False
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


class MidiPedal(Pedal):
	#Strymon Pedals are the only Pedals not routed through the looper
	commands = {"DATA_BYTE_ON":"\x7F", "DATA_BYTE_OFF":"\x00", "DATA_BYTE":"\x0F", 
		"PRESET_GROUP_0":"\x00\x00", "PRESET_GROUP_1":"\x00\x01", "PRESET_GROUP_2":"\x00\x02", 
		"ENGAGE_CC":"\x66", "BYPASS_CC":"\x66", "TAP_CC":"\x5D", "TOGGLEBYPASS_CC":"\x1D"}

	def __init__(self, name, state, MIDIchannel, commands, preset):
		type = "MidiPedal"
		self.MIDIchannel = MIDIchannel
		self.midi = MIDI.MIDI(self.MIDIchannel)
		self.preset = preset
		self.MidiCommandDict = self.commands
		self.setPreset(self.preset)
		Pedal.__init__(self, name, state, type) 

	def turn_on(self):
			#turn on via MIDI
			self.midi.MIDI_CC_TX(self.MidiCommandDict["ENGAGE_CC"], self.MidiCommandDict["DATA_BYTE_ON"])
			self.is_engaged = True
			logger.info(self.name + " on.")

	def turn_off(self):
		#turn off via MIDI
		self.midi.MIDI_CC_TX(self.MidiCommandDict["BYPASS_CC"], self.MidiCommandDict["DATA_BYTE_OFF"])
		self.is_engaged = False
		logger.info(self.name + " off.")

	def setPreset(self, preset):
		self.preset = preset
		presetGroup = preset / 128
		preset = preset % 128
		# self.midi.StrymonPresetChange(self.MidiCommandDict["PRESET_GROUP_" + str(presetGroup)], chr(preset))

	def setSelahPreset(self, preset):
		self.preset = preset
		self.midi.SelahPresetTempoChange(chr(preset))
	    	
	def set_setting(self, setting):
		pass
		# self.setStrymonPreset(int(setting))
		# self.setSelahPreset(int(setting))
		

# class TimeLine(MidiPedal):
    
# 	TimeLineSysExTempoStart = "\xF0\x00\x01\x55\x12\x01\x6F\x00\x00\x00" 
# 	TimeLineSysExEnd= "\xF7"

# 	def __init__(self, name, state, MIDIchannel, brand, tempo, preset):
# 		self.type = "TimeLine"
# 		self.tempo = tempo
# 		super(TimeLine, self).__init__(name, state, MIDIchannel, brand, preset)
# 		self.setTempo(self.tempo)

# 	def setTempo(self, tempo):
# 		#set tempo via MIDI
# 		self.delayInMs = int(60000/tempo)
# 		self.midi.SysEx_TX(self.TimeLineSysExTempoStart + chr(self.delayInMs//128) + chr(self.delayInMs%128) 
# 			+ self.TimeLineSysExEnd)

# 	def tapTempo(self):
# 		self.midi.MIDI_CC_TX(self.MidiCommandDict["TAP_CC"], self.MidiCommandDict["DATA_BYTE"])