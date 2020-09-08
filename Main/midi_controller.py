#!/usr/bin/python
import logging
import math
import sys
import time
from os import path
from traceback import format_exception
from flask import request, jsonify
from flask_cors import CORS

import RPi.GPIO as GPIO  # for interfacing with raspberrypi GPIO
import yaml
import EffectLoops  # package for controlling the midi devices
import Footswitches  # package for the footswitch inputs
import RotaryEncoder  # package for the rotary encoder inputs
import flask  # package for the webapp

switch_pins = Footswitches.Looper_Switches()  # class for dealing with footswitch presses
# set up rpi pins
# rotary encoder pins A & B go these pins on rpi
ENCODE_B = 23
ENCODE_A = 24
# MCP23017 output interrupt pins for bank A (0 - 7) and B (8 - 15) go to these pins on rpi
BANKA_INTPIN = 4
BANKB_INTPIN = 17
# these are input pins on the MCP23017 for the tap button and the rotary encoders push button
ROTARY_PUSHBUTTON_PINNUMBER = 15
CONFIG_FOLDER = "/home/pi/MidiController/Main/Conf/"
MIDI_PEDAL_CONF_FOLDER = CONFIG_FOLDER + "MidiPedals/"
CONFIG_FILE = CONFIG_FOLDER + "midi_controller.yaml"
rotary_push_button = None
footswitch_dict = {}
button_setup = {}
controller_api = {}
description_str = "Make button presses and return display text using python flask (CORS supported)."
app = flask.Flask(__name__)


def main():
    setup()
    try:
        while 1:
            time.sleep(0.1)
        # footswitch_dict['12'].setButtonDisplayMessage(strftime("%I:%M"),"")
    except KeyboardInterrupt:
        exc_type, exc_value, exc_tb = sys.exc_info()
        err_str = str(format_exception(exc_type, exc_value, exc_tb))
        logger.error("An exception was encountered: " + err_str)
    clean_break()


def setup():
    global rotary_push_button
    global footswitch_dict
    global button_setup
    global controller_api

    config_file = read_config_file()
    # read config dict's into more specific variables
    button_setup = {k: v for k, v in config_file['button_setup'].iteritems()}
    knob = {k: v for k, v in config_file['knob'].iteritems()}
    current_settings = {k: v for k, v in config_file['current_settings'].iteritems()}
    midi = {k: v for k, v in config_file['midi'].iteritems()}
    controller_api = {k: v for k, v in config_file['controller_api'].iteritems()}

    # read config objects into variables
    # tempo = float(current_settings['tempo'])
    knob_color = knob['color']
    knob_brightness = int(knob['brightness'])
    mode = current_settings['mode']
    set_list = current_settings['preset']['setList']
    song = current_settings['preset']['song']
    part = current_settings['preset']['part']

    # make a dictionary of {midi_channel: midi_obj}
    midi_channel_dict = {}
    channels = midi['channels']
    for channel in channels.keys():
        channel_dict = channels[channel]
        if isinstance(channel_dict, dict):
            channel_name = channels[channel].get('name', '')
            if channel_name:
                pedal_conf = MIDI_PEDAL_CONF_FOLDER + channel_name + '.yaml'
                if path.exists(pedal_conf):
                    # read midi config yaml file into dictionaries
                    with open(pedal_conf, 'r') as ymlfile:
                        midi_conf = yaml.full_load(ymlfile)
                    midi_channel_dict.update({
                        channel_name: EffectLoops.MidiPedal(channels[channel]['name'],
                                                            bool(channels[channel]['state']), int(channel), midi_conf,
                                                            channels[channel]['preset'].get('number',
                                                                                            channels[channel][
                                                                                                'preset'].get('name')))
                    })
                else:
                    logger.error(
                        'Cant add ' + channel_name + ' to the dictionary because it doesnt have a config file in '
                        + MIDI_PEDAL_CONF_FOLDER + '.')

    # make a dictionary of {ftsw_btn: footswitch_obj}
    footswitch_dict = {}
    # initialize the rotary encoder object
    rotary_push_button = RotaryEncoder.RotaryPushButton(ROTARY_PUSHBUTTON_PINNUMBER, mode,
                                                        kc=knob_color, kb=knob_brightness, sl=set_list, s=song,
                                                        p=part, buttons_locked=bool(controller_api['buttons_locked']))
    footswitch_dict[str(rotary_push_button.get_pin())] = rotary_push_button  # assign this button to the dictionary

    for ftsw_btn in button_setup.keys():
        ft_sw_obj = EffectLoops.ButtonOnPedalBoard(button_setup[ftsw_btn]['function'],
                                                   button_setup[ftsw_btn].get('partner_func', None),
                                                   button_setup[ftsw_btn].get('long_press_func', None), ftsw_btn)
        footswitch_dict.update({
            str(ft_sw_obj.get_pin()): ft_sw_obj
        })

    # pass a list of midi_pedal objects to the rotary encoder
    rotary_push_button.set_midi_pedal_list(midi_channel_dict, mode)

    # define the input pin on the rpi for the MCP23017 bank A and B footswitch interrupt
    GPIO.setup([BANKA_INTPIN, BANKB_INTPIN], GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
    # define the input pin on the rpi for the MCP23017 encode A and B input pins
    GPIO.setup([ENCODE_B, ENCODE_A], GPIO.IN, pull_up_down=GPIO.PUD_UP)

    # assign each footswitch (aside from rotary push button) a partner footswitch for double
    # footswitch press 'special functions'
    for pin in footswitch_dict:
        button = footswitch_dict[pin]
        if isinstance(button, EffectLoops.ButtonOnPedalBoard) and button.name != "RotaryPB":
            button.set_partner(footswitch_dict.get(str(button.from_button_to_pin(button.get_partner_button())), None))

    # define the interrupt for the MCP23017 bank A and B for the footswitches
    GPIO.add_event_detect(BANKA_INTPIN, GPIO.RISING, callback=my_button_callback, bouncetime=5)
    GPIO.add_event_detect(BANKB_INTPIN, GPIO.RISING, callback=my_button_callback, bouncetime=5)
    # define the interrupt for the MCP23017 encode pin A and B for the rotary encoder
    GPIO.add_event_detect(ENCODE_A, GPIO.BOTH, callback=my_encoder_callback)
    GPIO.add_event_detect(ENCODE_B, GPIO.BOTH, callback=my_encoder_callback)
    init_web_app()


def read_config_file(node=None):
    # read config yaml file into dictionaries
    with open(CONFIG_FILE, 'r') as ymlfile:
        config_file = yaml.full_load(ymlfile)
    if node:
        return config_file.get(node, None)
    else:
        return config_file


def init_web_app():
    CORS(app)
    app.config["DEBUG"] = True
    web_app_port = controller_api.get('port', None)
    if not web_app_port:
        web_app_port = 8090
    app.run(host='0.0.0.0', port=int(web_app_port), use_reloader=False)


def buttons_are_locked():
    controller_current_config = read_config_file("controller_api")
    return True if controller_current_config.get("buttons_locked", None) else False


def init_logging():
    """   ############ USAGE ###############
    logger.info("info message")
    logger.warning("warning message")
    logger.error("error message")
    """
    logging_logger = logging.getLogger(__name__)
    logging_logger.setLevel(logging.DEBUG)
    logging_logger.propagate = False
    # create console handler and set level to info
    handler = logging.StreamHandler()
    handler.setLevel(logging.INFO)
    formatter = logging.Formatter("%(asctime)s [midi_controller.py] [%(levelname)-5.5s]  %(message)s")
    handler.setFormatter(formatter)
    logging_logger.addHandler(handler)
    return logging_logger


def get_button_function_dict(button):
    return button_setup.get(int(button), None)


@app.route('/', methods=['GET'])
def home():
    logger.info("controller_api: " + description_str)
    return jsonify(controller_api=description_str)


@app.route('/midi_controller/short/<button>', methods=['GET'])
def short_button_press(button):
    bttn_func_dict = get_button_function_dict(button)
    handle_button_request(bttn_func_dict, button, "function", rotary_push_button.button_executor)
    return jsonify(display_message=rotary_push_button.get_message(), controller_locked=buttons_are_locked())


@app.route('/midi_controller/long/<button>', methods=['GET'])
def long_button_press(button):
    bttn_func_dict = get_button_function_dict(button)
    handle_button_request(bttn_func_dict, button, "long_press_func", rotary_push_button.change_and_select)
    return jsonify(display_message=rotary_push_button.get_message(), controller_locked=buttons_are_locked())


@app.route('/midi_controller/dpad/<direction>', methods=['GET'])
def dpad_button_press(direction):
    handle_dpad_request(direction)
    return jsonify(display_message=rotary_push_button.get_message(), controller_locked=buttons_are_locked())


@app.route('/help', methods=['GET'])
def help_request():
    message = "This is the help message."
    logger.info(message)
    return jsonify(display_message=message)


@app.errorhandler(404)
def page_not_found(e):
    logger.error("404: The resource could not be found.")
    return jsonify(display_message="Error.")


def handle_button_request(bttn_func_dict, button, config_button_press_type, func_to_execute):
    if bttn_func_dict:
        bttn_func = bttn_func_dict.get(config_button_press_type, None)
        handle_button_action(button, bttn_func, func_to_execute)
    else:
        logger.error("A " + str(press_length) + " press button request was made on the \"" + str(button)
                     + "\" button using the controller API. A function does not exist in the config file.")


def handle_dpad_request(direction):
    if direction in ['CW', 'CCW']:
        rotary_push_button.change_menu_pos(direction)
    elif direction == 'up':
        rotary_push_button.handle_long_press()
    elif direction == 'down':
        rotary_push_button.handle_short_press()
    else:
        logger.warn("No action taken for invalid direction: " + direction)


def handle_button_action(button, bttn_func, execution_func):
    if not buttons_are_locked():
        logger.info("running button function: " + str(bttn_func))
        execution_func(bttn_func)
        logger.info("A button press request was made on the \"" + str(button)
                    + "\" button using the controller API. Function = " + str(bttn_func))
    else:
        logger.warn("Failed! BUTTONS ARE LOCKED! A button press request was made on the \"" + str(button)
                    + "\" button using the controller API.")


def my_encoder_callback(encoder_interrupt_pin):
    direction = rotary_push_button.get_rotary_movement(GPIO.input(ENCODE_A), GPIO.input(ENCODE_B))
    if direction is not None:
        rotary_push_button.change_menu_pos(direction)


def my_button_callback(interrupt_pin):
    # logger.info("interrupt enter")
    # Which bank sent the interrupt; bank A (pin 4) mod 2 is 0; bank B (pin 17) mod 2 is 1
    interrupt_bank = interrupt_pin % 2
    # read the interrupt register; find which pin and bank that caused the interrupt
    pin_caused_int = switch_pins.interrupt_flag_register(interrupt_bank)
    # if the pin is equal to zero, interrupt should not happen
    if pin_caused_int != 0:
        # doing a read on the interrupt register returns an 8 bit binary number
        # where pin n returns 2^n. log returns a floating point so turn that into a integer
        # and add 8 for bank B. interrupt bank is either 0 or 1 from above.
        int_flag_pin = int(math.log(pin_caused_int, 2)) + 8 * interrupt_bank
        # logger.info("bank: " + str(interrupt_bank) + "; pin: " +
        # str(intFlagPin) + "; interrupt  Register = " + str(pin_caused_int))
        # look up the button object that caused the interrupt and assign it to interrupt button
        int_button = footswitch_dict[str(int_flag_pin)]
        time.sleep(.005)
        # disable the interrupts for that particular pin until the read of the value of that pin at the time of
        # the interrupt is complete other wise the interrupt would be reset on read.
        switch_pins.disable_interrupt_pin(int_flag_pin)
        # read value of the pin that caused the interrupt at the time of the interrupt
        interrupt_value = switch_pins.read_interrupt_cap_pin(int_flag_pin)
        # logger.info(int_button.name + "\'s interrupt pin's value: " + str(interrupt_value))
        # rotary push button does not have a "partner" so no need to check that one
        if int_button.name != "RotaryPB":
            # print interrupt_bank, intFlagPin #TESTING PURPOSES
            # check to see if the footswitch was pressed in combination with its partner for the 2-button function
            # like bank up, bank down, next song, etc.
            if int_button.partner and int_button.partner.is_pressed:
                if interrupt_value:
                    logger.info("partner func activated.")
                    func_name = int_button.get_partner_function()
                    if func_name:
                        rotary_push_button.change_and_select(func_name)
            else:
                # button state determines which function of the btn whose footswitch was pressed to use
                action = int_button.button_state(interrupt_value, rotary_push_button.mode)
                # logger.info("interrupt button's action: " + str(action))
                if interrupt_value:
                    if rotary_push_button.mode == "standard":
                        if time.time() - int_button.last_action_time <= 0.5:
                            logger.info("running standard button function: " + str(action))
                            rotary_push_button.button_executor(action)
                        else:
                            logger.info("running longpress button function: " + str(action))
                            rotary_push_button.change_and_select(action)
                    else:
                        logger.info("in favorite mode, this action (" + str(action) + ") is not permitted")
            int_button.last_action_time = time.time()
        else:
            # logger.info("rotary func")
            # button state determines which function of the btn whose footswitch was pressed to use
            int_button.button_state(interrupt_value)
        # enable the interrupts on the pin of the footswitch that was pressed
        switch_pins.enable_interrupt_pin(int_flag_pin)


def clean_break():
    rotary_push_button.clean_up_display()
    rotary_push_button.stop_pwm()  # this will cause the PWM to stop if anything causes the program to stop
    EffectLoops.unload()


if __name__ == "__main__":
    global logger
    logger = init_logging()
    main()
