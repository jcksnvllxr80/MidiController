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

	def __init__(self, name, state):
		self.name = name
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
					if delta_t < 0.5:
						output = self.name
					else:
						output = "secondary func"
			else:
				output = "partner func"
				self.partner.PedalConfigChanged = False
			self.is_pressed = False
		return output


	def from_button_to_pin(self, button):
		button_to_pin_dict = {1:0, 2:1, 3:2, 4:8, 5:10, 15:15}
		return button_to_pin_dict.get(button, None)


	def set_partner(self, partner):
		if partner:
			self.partner = partner
			self.partner.partner = self


	def get_partner_button(self):
		partner_dict = {1: 4, 2:15, 3: 5, 4: 1, 5: 3, 15:2}
		return partner_dict.get(self.button, None)



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

	def __init__(self, name, state, midi_channel, commands, preset):
		self.midi_channel = midi_channel
		self.midi = MIDI.MIDI(self.midi_channel)
		self.midi_command_dict = commands
		Pedal.__init__(self, name, state)
		self.set_preset(preset) 


	def turn_on(self):
		engage_dict = self.midi_command_dict.get("Engage", None)
		if engage_dict:
			self.determine_action_method(engage_dict)
			pass 
			self.is_engaged = True
			logger.info(self.name + " on.")
		else:
			logger.info(self.name + " has no \'Engage\' option defined in the pedal config.")


	def turn_off(self):
		bypass_dict = self.midi_command_dict.get("Bypass", None)
		if bypass_dict:
			self.determine_action_method(bypass_dict)
			pass 
			self.is_engaged = False
			logger.info(self.name + " off.")
		else:
			logger.info(self.name + " has no \'Bypass\' option defined in the pedal config.")


	def set_preset(self, preset):
		self.preset = preset
		set_preset_dict = self.midi_command_dict.get("Set Preset", None)
		if set_preset_dict:
			self.determine_action_method(set_preset_dict, preset)
			pass
		else:
			logger.info(self.name + " has no \'Set Preset\' option defined in the pedal config.")


	def set_setting(self, setting):
		pass


	def determine_action_method(self, action_dict, value=None):
		if value is None:
			value = action_dict.get('value', None)
		if action_dict.get('cc', None):
			value = self.check_for_func(action_dict, value)
			self.midi.midi_cc_tx(chr(action_dict['cc']), chr(value))
		elif action_dict.get('program change', None):
			value = self.check_for_func(action_dict['program change'], value)
			self.midi.midi_pc_tx(chr(value))
		elif action_dict.get('multi', None):
			self.handle_multi_functions(action_dict, value)


	def check_for_func(self, change_dict, v):
		new_v = v
		if change_dict.get('func', None):
			f = eval('lambda x: ' + change_dict['func'])
			new_v = f(v)
		return new_v


	def handle_multi_functions(self, action_dict, val):
		actions = action_dict['multi']
		for i in range(len(actions)):
			# logger.info('actions dictionary: ' + str(actions))
			todo_item = actions[i + 1]
			if action_dict.get(todo_item, None):
				todo = action_dict[todo_item]
				if todo.get('cc', None):
					val = self.check_for_func(todo, val)
					self.midi.midi_cc_tx(chr(todo['cc']), chr(val))
				elif todo.get('program change', None):
					val = self.check_for_func(todo['program change'], val)
					self.midi.midi_pc_tx(chr(val))