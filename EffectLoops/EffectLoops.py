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

	def __init__(self, name, partner_function, long_press_func, button, **kwargs):
		self.name = name
		self.button = button
		self.start = time.time()
		self.pin = self.from_button_to_pin(self.button)
		self.is_pressed = False
		self.partner = None
		self.partner_function = partner_function
		self.long_press_func = long_press_func
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
			if (self.partner and (not self.partner.PedalConfigChanged or time.time() - self.partner.last_action_time > 0.25)) or not self.partner:
				if delta_t < 0.5:
					output = self.name
				else:
					output = self.secondaryFunction()
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
		partner_dict = {} # {1: 4, 3: 5, 4: 1, 5: 3}
		return partner_dict.get(self.button, None)


	def secondaryFunction(self):
		return self.long_press_func


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
		logger.info("setting " + str(setting))


	def get_partner_function(self):
		return self.partner_function


class MidiPedal(Pedal):

	def __init__(self, name, state, midi_channel, commands, preset):
		self.midi_channel = midi_channel
		self.midi = MIDI.MIDI(self.midi_channel)
		self.midi_command_dict = commands
		Pedal.__init__(self, name, state)
		try:
			preset = int(preset)
		except ValueError:
			logging.info("Cant cast \'" + preset + "\' as an interger. Assuming it is a name based preset.")
		self.set_preset(preset) 


	def turn_on(self):
		engage_dict = self.midi_command_dict.get("Engage", None)
		if engage_dict:
			self.determine_action_method(engage_dict)
			self.is_engaged = True
			logger.info(self.name + " on.")
		else:
			logger.info(self.name + " has no \'Engage\' option defined in the pedal config.")


	def turn_off(self):
		bypass_dict = self.midi_command_dict.get("Bypass", None)
		if bypass_dict:
			self.determine_action_method(bypass_dict)
			self.is_engaged = False
			logger.info(self.name + " off.")
		else:
			logger.info(self.name + " has no \'Bypass\' option defined in the pedal config.")


	def set_preset(self, preset):
		self.preset = preset
		set_preset_dict = self.midi_command_dict.get("Set Preset", None)
		if set_preset_dict:
			self.determine_action_method(set_preset_dict, self.preset)
			logger.info(self.name + " preset was set to " + str(self.preset) + ".")
		else:
			logger.info(self.name + " has no \'Set Preset\' option defined in the pedal config.")


	def set_setting(self, setting):
		setting_dict = self.midi_command_dict.get(setting, None)
		if setting_dict:
			self.determine_action_method(setting_dict, setting)
			logger.info(self.name + " setting " + str(setting) + " set.")
		else:
			logger.info(self.name + " setting " + str(setting) + " was not found in the pedal config.")


	def set_params(self, params):
		params_dict = self.midi_command_dict.get("Parameters", None)
		if params_dict:
			for param, value in params.iteritems():
				param_info = params_dict.get(param, None)
				if param_info:
					param_was_set = self.determine_parameter_method(param_info, param, value)
					if param_was_set:
						logger.info(self.name + " parameter " + str(param) + " set.")
					else:
						logger.info(self.name + " parameter " + str(param) + " not set.")
				else:
					logger.info("Parameter: " + str(param) + ", not found in " + self.name + " param dict -> " + str(params_dict))
		else:
			logger.info(self.name + " parameters dictionary was not found in the pedal config.")


	def determine_parameter_method(self, action_dict, parameter, value=None):
		param_set = False
		if value is None:
			value = action_dict.get('value', None)
		if action_dict.get('cc', None):
			value = self.check_for_func(action_dict, value)
			value = self.check_value_for_engaged(value)
			logger.info("Value is \'" + str(value) + "\' after check_value_for_engaged function.")
			value = self.convert_to_int(action_dict, value)
			logger.info("Value is \'" + str(value) + "\' after convert_to_int function.")
			if value:
				self.midi.midi_cc_tx(chr(action_dict['cc']), chr(value))
				param_set = True
		return param_set
		# elif action_dict.get('program change', None):
		# 	value = self.check_for_func(action_dict['program change'], value)
		# 	self.midi.midi_pc_tx(chr(value))
		# elif action_dict.get('control change', None):
		# 	# logger.info(self.name + " has a value of " + str(value) + " before going through lambda func.")
		# 	value = self.check_for_func(action_dict['control change'], value)
		# 	# logger.info(self.name + " has a value of " + str(value) + " after going through lambda func.")
		# 	self.midi.midi_cc_tx(chr(value))
		# elif action_dict.get('multi', None):
		# 	self.handle_multi_functions(action_dict, value)


	def determine_action_method(self, action_dict, value=None):
		if value is None:
			value = action_dict.get('value', None)
		if action_dict.get('cc', None):
			value = self.check_for_func(action_dict, value)
			self.midi.midi_cc_tx(chr(action_dict['cc']), chr(value))
		elif action_dict.get('program change', None):
			value = self.check_for_func(action_dict['program change'], value)
			self.midi.midi_pc_tx(chr(value))
		elif action_dict.get('control change', None):
			# logger.info(self.name + " has a value of " + str(value) + " before going through lambda func.")
			value = self.check_for_func(action_dict['control change'], value)
			# logger.info(self.name + " has a value of " + str(value) + " after going through lambda func.")
			self.midi.midi_cc_tx(chr(value))
		elif action_dict.get('multi', None):
			self.handle_multi_functions(action_dict, value)


	def convert_to_int(self, change_dict, v):
		converted_to_int = None
		try:
			dict_val = change_dict.get(v, None)
			if dict_val:
				converted_to_int = int(dict_val)
			else:
				logger.info("Key: " + str(v) + ", not found in dict -> " + str(change_dict))
		except ValueError:
			logger.error("Value \'" + str(v) + "\' cannot be converted to an int.")
		return converted_to_int


	def check_for_func(self, change_dict, v):
		new_v = v
		if change_dict.get('func', None):
			f = eval('lambda x: ' + change_dict['func'])
			new_v = f(v)
		return new_v


	def check_value_for_engaged(self, v):
		new_v = v
		if isinstance(v, dict):
			engaged = v.get('engaged', None)
			if engaged is not None:
				return engaged
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