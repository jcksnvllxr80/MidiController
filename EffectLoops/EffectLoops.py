# 2016
# Author: Aaron Watkins

import time
import MIDI
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
handler.setLevel(logging.DEBUG)
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
        return self.name + " " + self.get_state()

    def get_state(self):
        if self.is_engaged:
            return "Engaged"
        else:
            return "Bypassed"


class ButtonOnPedalBoard(object):

    def __init__(self, name, partner_function, long_press_func, button, **kwargs):
        self.name = name
        self.is_engaged = None
        self.end = None
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
            if (self.partner and (
                    not self.partner.PedalConfigChanged or time.time() - self.partner.last_action_time > 0.25)) \
                    or not self.partner:
                if delta_t < 0.5:
                    output = self.name
                else:
                    output = self.secondary_function()
            else:
                output = "partner func"
                self.partner.PedalConfigChanged = False
            self.is_pressed = False
        return output

    @staticmethod
    def from_button_to_pin(button):
        button_to_pin_dict = {1: 0, 2: 1, 3: 2, 4: 8, 5: 10, 15: 15}
        return button_to_pin_dict.get(button, None)

    def set_partner(self, partner):
        if partner:
            self.partner = partner
            self.partner.partner = self

    def get_partner_button(self):
        partner_dict = {}  # {1: 4, 3: 5, 4: 1, 5: 3}
        return partner_dict.get(self.button, None)

    def secondary_function(self):
        return self.long_press_func

    def turn_on(self):
        self.is_engaged = True
        logger.info(self)

    def turn_off(self):
        if self.name != "Empty":
            self.is_engaged = False
        logger.info(self)

    def get_pin(self):
        return self.pin

    @staticmethod
    def set_setting(setting):
        logger.info("setting " + str(setting))

    def get_partner_function(self):
        return self.partner_function


class MidiPedal(Pedal):
    params_types = ['Knobs/Switches', 'Parameters']

    def __init__(self, name, state, midi_channel, commands, preset):
        self.preset = preset
        self.midi_channel = midi_channel
        self.midi = MIDI.MIDI(self.midi_channel)
        self.midi_command_dict = commands
        self.midi_pedal_conf_dict = {
            "Parameters": self.midi_command_dict.get("Parameters", None),
            "Engage": self.midi_command_dict.get("Engage", None),
            "Bypass": self.midi_command_dict.get("Bypass", None),
            "Set Preset": self.midi_command_dict.get("Set Preset", None),
            "Set Tempo": self.midi_command_dict.get("Set Tempo", None),
            "Knobs/Switches": self.midi_command_dict.get("Knobs/Switches", None),
            "Toggle Bypass": self.midi_command_dict.get("Toggle Bypass", None)
        }
        Pedal.__init__(self, name, state)
        try:
            preset = int(preset)
        except ValueError:
            logging.info("Cant cast \'" + str(preset) + "\' as an integer. Assuming it is a name based preset.")
        self.set_preset(preset)

    def turn_on(self):
        if self.midi_pedal_conf_dict["Engage"]:
            self.determine_action_method(self.midi_pedal_conf_dict["Engage"])
            self.is_engaged = True
            logger.info(self.name + " on.")
        else:
            logger.info(self.name + " has no \'Engage\' option defined in the pedal config.")

    def turn_off(self):
        if self.midi_pedal_conf_dict["Bypass"]:
            self.determine_action_method(self.midi_pedal_conf_dict["Bypass"])
            self.is_engaged = False
            logger.info(self.name + " off.")
        else:
            logger.info(self.name + " has no \'Bypass\' option defined in the pedal config.")

    def toggle_engaged(self):
        if self.midi_pedal_conf_dict["Toggle Bypass"]:
            self.determine_action_method(self.midi_pedal_conf_dict["Toggle Bypass"])
            self.is_engaged ^= True
            logger.info(self.name + " on." if self.is_engaged else " off.")
        else:
            logger.info(self.name + " has no \'Toggle Bypass\' option defined in the pedal config.")

    def set_preset(self, preset):
        if self.midi_pedal_conf_dict["Set Preset"]:
            if preset == '':
                logger.info(self.name + " has no preset for this part.")
            else:
                self.determine_action_method(self.midi_pedal_conf_dict["Set Preset"], preset)
                logger.info(self.name + " preset was set to " + str(preset) + ".")
                self.preset = preset
        else:
            logger.info(self.name + " has no \'Set Preset\' option defined in the pedal config.")

    def set_tempo(self, tempo):
        if self.midi_pedal_conf_dict["Set Tempo"]:
            if tempo == '':
                logger.info(self.name + " has no tempo for this part.")
            else:
                self.determine_action_method(self.midi_pedal_conf_dict["Set Tempo"], tempo)
                logger.info(self.name + " tempo was set to " + str(tempo) + ".")
        else:
            logger.info(self.name + " has no \'Set Tempo\' option defined in the pedal config.")

    def set_setting(self, setting):
        setting_dict = self.midi_command_dict.get(setting, None)
        if setting_dict:
            self.determine_action_method(setting_dict, setting)
            logger.info(self.name + " setting " + str(setting) + " set.")
        else:
            logger.info(self.name + " setting " + str(setting) + " was not found in the pedal config.")

    def set_params(self, params):
        for param, value in params.iteritems():
            for param_type in self.params_types:
                if self.midi_pedal_conf_dict[param_type]:
                    if self.set_param(param, value, param_type):
                        break  # break for the inner for loop and then find the next (param, value) pair

    def set_param(self, param, value, param_type):
        config_found = False
        param_info = self.midi_pedal_conf_dict[param_type].get(param, None)
        if param_info:
            config_found = self.check_for_param_then_set(config_found, param_info, param, value)
        else:
            logger.info("Configuration option, " + str(param) + ", not found in " + self.name + " \'" + param_type +
                        "\' configuration dict -> " + str(self.midi_pedal_conf_dict[param_type]))
        return config_found

    def check_for_param_then_set(self, config_found, param_info, param, value):
        param_was_set = self.determine_parameter_method(param_info, value)
        if param_was_set:
            logger.info(self.name + " parameter \'" + str(param) + "\' set to " + str(value) + ".")
            config_found = True
        else:
            logger.info(self.name + " parameter \'" + str(param) + "\' not set.")
        return config_found

    def determine_parameter_method(self, action_dict, value=None):
        param_set = False
        if value is None:
            value = action_dict.get('value', None)
        if action_dict.get('cc', None):
            value = self.check_for_func(action_dict, value)
            value = self.check_value_for_engaged(value)
            logger.debug("Value is \'" + str(value) + "\' after check_value_for_engaged function.")
            value = self.convert_to_int(action_dict, value)
            logger.debug("Value is \'" + str(value) + "\' after convert_to_int function.")
            if value is not None:
                self.midi.midi_cc_tx(chr(action_dict['cc']), chr(value))
                param_set = True
        if not param_set:
            logger.debug("Uh oh! Could not set param to \'{0}\' for some reason.".format(str(value)))
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
            logger.debug(self.name + " has a value of " + str(value) + " before going through lambda func.")
            value = self.check_for_func(action_dict['control change'], value)
            logger.debug(self.name + " has a value of " + str(value) + " after going through lambda func.")
            self.midi.midi_cc_tx(chr(value))
        elif action_dict.get('multi', None):
            self.handle_multi_functions(action_dict, value)

    @staticmethod
    def convert_to_int(change_dict, v):
        converted_to_int = None
        try:
            dict_val = change_dict.get(v, change_dict.get('dict', {}).get(v, None))
            if dict_val is not None:
                converted_to_int = int(dict_val)
            elif change_dict.get('value', None) == v:
                logger.info("This param uses key \'value\' and the value is " + str(v) + ". ")
                converted_to_int = int(v)
            elif isinstance(v, bool):
                v = 'on' if v else 'off'
            else:
                logger.info("Key, " + str(v) + ", not found in dict -> " + str(change_dict))
                min_val = change_dict.get('min', None)
                max_val = change_dict.get('max', None)
                if min_val is not None and max_val is not None:
                    val = int(v)
                    if min_val <= val <= max_val:
                        converted_to_int = val
                    else:
                        logger.info("The value, " + str(v) + ", is not in the range [" + str(min_val) + ", " + str(
                            max_val) + "]")
        except ValueError:
            logger.error("Value \'" + str(v) + "\' cannot be converted to an int.")
        return converted_to_int

    @staticmethod
    def check_for_func(change_dict, v):
        new_v = v
        if change_dict.get('func', None):
            f = eval('lambda x: ' + change_dict['func'])
            new_v = f(v)
        return new_v

    @staticmethod
    def check_value_for_engaged(v):
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
