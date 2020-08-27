# import python packages
import logging
import os
import subprocess
import threading
import time

import RPi.GPIO as GPIO
import yaml
from numpy import arange, cos

import EffectLoops
import N_Tree
import OledDisplay
import PartSongSet

"""   ############ USAGE ###############
logger.info("info message")
logger.warning("warning message")
logger.error("error message")
"""
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
logger.propagate = False
# create console handler and set level to info
handler = logging.StreamHandler()
handler.setLevel(logging.DEBUG)
formatter = logging.Formatter("%(asctime)s [RotaryEncoder.py] [%(levelname)-5.5s]  %(message)s")
handler.setFormatter(formatter)
logger.addHandler(handler)

SET_FOLDER = "/home/pi/MidiController/PartSongSet/Sets/"
MIDI_PEDAL_CONF_FOLDER = "/home/pi/MidiController/Main/Conf/MidiPedals/"
CONFIG_FILE = "/home/pi/MidiController/Main/Conf/midi_controller.yaml"


# define class for the PWM driver for the colors part of the rotary knob
class RgbKnob(object):
    # GPIO pin on rpi
    RED_PIN = 16
    GREEN_PIN = 20
    BLUE_PIN = 21
    # global variables
    FREQ = 1000
    COLORS = ["Off", "Blue", "Green", "Cyan", "Red", "Magenta", "Yellow", "White"]
    STATS = ["IP", "Stats"]

    def __init__(self, knob_color):
        self._red = None
        self._green = None
        self._blue = None
        self.brightness = None
        self.color = None
        self.r = None
        self.g = None
        self.b = None
        self.all_midi_pedals = None
        self.midi_pedal_dict = {}
        col, val = knob_color
        self.init_pwm()  # initialize GPIO for PWM
        self.set_color(col, val)  # starting color
        self.start_pwm()  # start the PWM
        self.displaying_current_songpart = True

    def init_pwm(self):
        """ set the mode for how the GPIO pins will be numbered """
        GPIO.setmode(GPIO.BCM)
        # set the list of pin numbers as outputs
        GPIO.setup([self.RED_PIN, self.GREEN_PIN, self.BLUE_PIN], GPIO.OUT)
        # set freq and pin number to a PWM object for each of the 3 RGB components
        self._red = GPIO.PWM(self.RED_PIN, self.FREQ)
        self._green = GPIO.PWM(self.GREEN_PIN, self.FREQ)
        self._blue = GPIO.PWM(self.BLUE_PIN, self.FREQ)

    def start_pwm(self):
        """ start PWM with (100 - x) dutyCycle """
        self._red.start(100 - self.r)
        self._green.start(100 - self.g)
        self._blue.start(100 - self.b)

    def stop_pwm(self):
        """ stop the PWM """
        self._red.stop()
        self._green.stop()
        self._blue.stop()
        GPIO.cleanup()
        logger.info("Stopped PWM for the rotary pb.")

    def set_brightness(self, v):
        """ change the global brightness variable and apply to the current color """
        self.brightness = v
        self.set_color(self.color)

    def set_color(self, color, v=None):
        """ changes the color of the rotary encoder knob """
        new_color = color
        self.color = new_color
        if v is not None:
            self.brightness = v
        else:
            v = self.brightness
        # depending on the color string set the individual components r, g, and b
        if new_color == self.COLORS[0]:
            self.r, self.g, self.b = (0, 0, 0)
        elif new_color == self.COLORS[1]:
            self.r, self.g, self.b = (0, 0, v)
        elif new_color == self.COLORS[2]:
            self.r, self.g, self.b = (0, v, 0)
        elif new_color == self.COLORS[3]:
            self.r, self.g, self.b = (0, v, v)
        elif new_color == self.COLORS[4]:
            self.r, self.g, self.b = (v, 0, 0)
        elif new_color == self.COLORS[5]:
            self.r, self.g, self.b = (v, 0, v)
        elif new_color == self.COLORS[6]:
            self.r, self.g, self.b = (v, v, 0)
        elif new_color == self.COLORS[7]:
            self.r, self.g, self.b = (v, v, v)
        # update the duty cycle since duty cycle is how brightness is realized
        self.set_rgb_duty_cycle()

    def set_rgb_duty_cycle(self, multiplier=1):
        """ update the duty cycle for each component of RGB """
        self._red.ChangeDutyCycle((100 - self.r * multiplier))
        self._green.ChangeDutyCycle((100 - self.g * multiplier))
        self._blue.ChangeDutyCycle((100 - self.b * multiplier))

    def pulsate(self):
        """ pulsate the rgb knob color """
        x = range(0, 62)
        i = 0
        while not self.displaying_current_songpart:
            self.set_rgb_duty_cycle(abs(cos(x[i] / (2 * 3.14))))
            if i <= 40:
                i += 1
            else:
                i = 0
            time.sleep(0.05)
        self.set_rgb_duty_cycle()  # restore the brightness multiplier of 1


class RotaryEncoder(RgbKnob):
    """ class for everything to do with the rotary encoder. its parent is RgbKnob """

    # NOTE: Need to always display song info (main menu / root of menu tree)
    # on 1 short click go to song/set/part/bpm/midi_pedal menu
    # on 2 second click got to global menu
    # on 5 second click go to power off menu

    # build menu with N_Tree
    menu = N_Tree.N_Tree("MidiController")
    setup_menu = menu.root.add_child("Setup")
    global_menu = menu.root.add_child("Global")
    midi_change_keys = ['cc', 'pc', 'program change', 'control change', 'multi']
    leaf_keys = ['min', 'max', 'on', 'off', 'value', 'dict', 'press', 'release']
    leaf_keys.extend(midi_change_keys)
    rotary_threads = []

    def __init__(self, **kwargs):
        knob_col = kwargs["kc"]
        knob_bright = kwargs["kb"]
        knob_color = (knob_col, knob_bright)
        previously_loaded_set = kwargs["sl"]
        previously_loaded_song = kwargs["s"]
        previously_loaded_part = kwargs["p"]
        # initialize parent class
        super(RotaryEncoder, self).__init__(knob_color)
        self.oled = OledDisplay.OledDisplay()
        # self.lcd = Adafruit_CharLCD.Adafruit_CharLCDPlate() #: " "has-a" lcd
        self.setlist = PartSongSet.Setlist()  # : " "has-a" Setlist
        self.displayed_msg = ""
        self.setlist_name = previously_loaded_set
        # load the set, song, and part that was last used that was saved to the default file
        self.setlist.load_setlist(SET_FOLDER + previously_loaded_set)
        self.current_song = self.setlist.songs.head
        while self.current_song.next is not None and previously_loaded_song != self.current_song.data.name:
            self.current_song = self.current_song.next
        self.current_part = self.current_song.data.parts.head
        while self.current_part.next is not None and previously_loaded_part != self.current_part.data.part_name:
            self.current_part = self.current_part.next
        self.displayed_song = self.current_song
        self.displayed_part = self.current_part
        self.displayed_song_index = self.setlist.songs.node_to_index(self.displayed_song)
        self.displayed_part_index = self.current_song.data.parts.node_to_index(self.displayed_part)
        logger.info("{displayed song index: " + str(self.displayed_song_index) + ", displayed part index: " + str(
            self.displayed_part_index) + "}")

        # set up the MidiController setup menus (set, seong, part, midi_pedal, bpm)
        self.setlist_menu = self.setup_menu.add_child("Sets", self.show_setlists, self.load_set_func)
        self.songs_menu = self.setup_menu.add_child("Songs", self.show_songs, self.load_song_func)
        self.parts_menu = self.setup_menu.add_child("Parts", self.show_parts, self.load_part_func)
        self.midi_pedal_menu = self.setup_menu.add_child("Midi Pedals",
                                                         self.show_midi_pedals)  # , self.load_midi_pedal_config_menu)
        # TODO: add this back if I even need BPM again. prob will.
        # self.bpm_menu = self.setup_menu.add_child("BPM", self.show_bpm, self.load_bpm_func)
        # don't let the tempo go below 40 or above 500
        self.tempo_range = arange(40, 500, 0.5).tolist()
        self.set_song_info_message()

        self.midi_pedal_config_menu = {}
        self.set_midi_pedal_conf_grps_menu()

        # define power menu
        self.power_menu = self.menu.root.add_child("Power", self.set_menu_data_message)
        self.power_menu.menu_data_prompt = "Power Off?"
        self.power_menu.menu_data_items = ["NO yes", "no YES"]
        self.power_menu.menu_data_dict = {"NO yes": self.change_menu_nodes, "no YES": self.power_off}

        # build global menu
        self.knob_color_menu = self.global_menu.add_child("Knob Color", self.show_knob_colors, self.load_color_func)
        self.knob_brightness_menu = self.global_menu.add_child("Knob Brightness", self.show_brightness,
                                                               self.load_brightness_func)
        self.about_menu = self.global_menu.add_child("About", self.show_about, self.load_about_func)

        # variables for the rotary movement interpretation loop
        self.last_good_seq = 0
        self.last_move = None

        # keeps time for last rotary turn in seconds
        self.last_rotary_turn = 0
        self.menu.current_node.current_child = 0

    def set_midi_pedal_conf_grps_menu(self):
        for midi_pedal_conf in os.listdir(MIDI_PEDAL_CONF_FOLDER):
            if midi_pedal_conf[-5:] == ".yaml":
                midi_pedal_name = midi_pedal_conf[:-5]
                self.midi_pedal_config_menu[midi_pedal_name] = \
                    self.midi_pedal_menu.add_child(midi_pedal_name, self.show_midi_pedal_configuration_groups)

    # TODO: this is broken. it should be a way to set the contents of the menu.
    def rebuild_menu(self):
        # build setup menu based on current files stored in filesystem
        pass

    def clean_up_display(self):
        self.oled.clear_display()

    def power_off(self):
        self.set_message("Goodbye.")
        self.oled._delay_microseconds(1000000)
        os.system('sudo shutdown now -h')

    def show_knob_colors(self):
        self.knob_color_menu.menu_data_items = RgbKnob.COLORS
        self.knob_color_menu.menu_data_prompt = self.knob_color_menu.name + ":"
        self.knob_color_menu.menu_data_position = RgbKnob.COLORS.index(self.color)
        self.test_point_node_printer(self.knob_color_menu)

    def show_brightness(self):
        self.knob_brightness_menu.menu_data_items = range(0, 101, 10)
        self.knob_brightness_menu.menu_data_prompt = self.knob_brightness_menu.name + ":"
        self.knob_brightness_menu.menu_data_position = self.knob_brightness_menu.menu_data_items.index(self.brightness)
        self.test_point_node_printer(self.knob_brightness_menu)

    def show_about(self):
        self.about_menu.menu_data_items = RgbKnob.STATS
        self.about_menu.menu_data_prompt = self.about_menu.name + ":"
        self.about_menu.menu_data_position = self.about_menu.menu_data_items.index('IP')
        self.test_point_node_printer(self.about_menu)

    @staticmethod
    def get_ip():
        cmd = "hostname -I | grep -Eo \"([0-9]{1,3}[\.]){3}[0-9]{1,3}\""  # "hostname -I | cut -d\' \' -f1"
        ip_addresses = subprocess.check_output(cmd, shell=True)
        return "IP: - " + str(ip_addresses.replace("\n", ' - '))

    @staticmethod
    def get_stats():
        cmd = "top -bn1 | grep load | awk '{printf \"CPU Load: %.2f\", $(NF-2)}'"
        cpu_usage = subprocess.check_output(cmd, shell=True)
        cmd = "free -m | awk 'NR==2{printf \"Mem: %s/%sMB %.2f%%\", $3,$2,$3*100/$2 }'"
        memory_usage = subprocess.check_output(cmd, shell=True)
        cmd = "df -h | awk '$NF==\"/\"{printf \"Disk: %d/%dGB %s\", $3,$2,$5}'"
        disk_usage = subprocess.check_output(cmd, shell=True)
        cmd = "/opt/vc/bin/vcgencmd measure_temp | egrep -o '[0-9]*\.[0-9]*' " \
              "| awk '{printf \"Temp: %.1f\xB0F/%.1f\xB0C\", ($1 * 9/5) + 32, $1}'"
        temperature = subprocess.check_output(cmd, shell=True)
        return str(cpu_usage) + " - " + str(memory_usage) + " - " + str(disk_usage) + " - " + str(temperature)

    def show_ip(self):
        self.oled.set_display_message(self.get_ip())

    # self.oled._delay_microseconds(5000000)

    def show_stats(self):
        self.oled.set_display_message(self.get_stats())

    # self.oled._delay_microseconds(5000000)

    def load_color_func(self):
        self.set_color(self.knob_color_menu.menu_data_items[self.knob_color_menu.menu_data_position])
        self.save_color_as_default()
        self.change_menu_nodes(self.knob_color_menu.parent)

    def load_brightness_func(self):
        self.set_brightness(self.knob_brightness_menu.menu_data_items[self.knob_brightness_menu.menu_data_position])
        self.save_color_as_default()
        self.change_menu_nodes(self.knob_brightness_menu.parent)

    def set_about(self, menu_item):
        if menu_item == "IP":
            self.show_ip()
        elif menu_item == "Stats":
            self.show_stats()

    def load_about_func(self):
        self.set_about(self.about_menu.menu_data_items[self.about_menu.menu_data_position])

    # self.change_menu_nodes(self.about_menu.parent)

    @staticmethod
    def test_point_node_printer(the_node):
        this_data_item = str(None)
        try:
            if the_node.menu_data_items:
                this_data_item = str(the_node.menu_data_items[the_node.menu_data_position])
            logger.info("\nnode: " + str(the_node) + "prompt: " + the_node.menu_data_prompt +
                        "\nitems: " + str(the_node.menu_data_items) + "\ncurrent item: " + this_data_item +
                        "\nposition: " + str(the_node.menu_data_position))
        except Exception as e:
            logger.exception(e)
            logger.error("Ran into an error trying to print using stuff using the following data:" +
                         "\nnode: " + str(the_node) +
                         "\nprompt: " + str(the_node.menu_data_prompt) +
                         "\ninserting this data position: " + str(the_node.menu_data_position) +
                         " into these items: " + str(the_node.menu_data_items) +
                         " produced this current item: " + this_data_item + ".")

    def show_setlists(self):
        # read setlist files from folder where they belong
        # display the first item in the list
        self.setlist_menu.menu_data_items = []
        self.setlist_menu.menu_data_prompt = self.setlist_menu.name + ":"
        setlist_files = os.listdir(SET_FOLDER)
        for setlist_file in setlist_files:
            if setlist_file[-5:] == ".yaml":
                self.setlist_menu.menu_data_items.append(setlist_file[:-5])
        self.test_point_node_printer(self.setlist_menu)

    def show_songs(self):
        self.songs_menu.menu_data_items = []
        self.songs_menu.menu_data_prompt = self.songs_menu.name + ":"
        logger.info(self.setlist.songs.show())
        for song in self.setlist.songs.to_list():
            logger.info(song)
            self.songs_menu.menu_data_items.append(song.name)
        self.test_point_node_printer(self.songs_menu)

    def show_parts(self):
        self.parts_menu.menu_data_items = []
        self.parts_menu.menu_data_prompt = self.parts_menu.name + ":"
        logger.info(self.current_song.data.parts.show())
        for part in self.current_song.data.parts.to_list():
            logger.info(part)
            self.parts_menu.menu_data_items.append(part.part_name)
        self.test_point_node_printer(self.parts_menu)

    def show_midi_pedals(self):
        self.midi_pedal_menu.menu_data_prompt = self.midi_pedal_menu.name + ":"
        self.midi_pedal_menu.menu_data_items = self.all_midi_pedals
        self.midi_pedal_menu.menu_data_position = self.menu_data_item_position_init(
            self.midi_pedal_menu.menu_data_position)
        self.test_point_node_printer(self.midi_pedal_menu)

    def show_midi_pedal_configuration_groups(self):
        midi_pedal_name = self.midi_pedal_menu.children[self.midi_pedal_menu.current_child].name
        self.midi_pedal_config_menu[midi_pedal_name].menu_data_items = []
        self.midi_pedal_config_menu[midi_pedal_name].menu_data_prompt = self.midi_pedal_config_menu[
                                                                            midi_pedal_name].name + ":"
        self.midi_pedal_config_menu[midi_pedal_name].menu_data_position = self.menu_data_item_position_init(
            self.midi_pedal_config_menu[midi_pedal_name].menu_data_position)
        midi_pedal_conf = self.midi_pedal_dict.get(midi_pedal_name, None)
        if midi_pedal_conf:
            for midi_pedal_conf_grp_key, midi_pedal_conf_grp_value in midi_pedal_conf.midi_pedal_conf_dict.iteritems():
                if midi_pedal_conf_grp_value:
                    self.midi_pedal_config_menu[midi_pedal_name].menu_data_items.append(midi_pedal_conf_grp_key)
                    self.midi_pedal_config_menu[midi_pedal_name].menu_data_dict.update(
                        {midi_pedal_conf_grp_key: midi_pedal_conf_grp_value})
                    self.set_midi_pedal_conf_grp_menu(midi_pedal_conf_grp_key,
                                                      self.midi_pedal_config_menu[midi_pedal_name])
        self.test_point_node_printer(self.midi_pedal_config_menu[midi_pedal_name])

    def set_midi_pedal_conf_grp_menu(self, midi_pedal_conf_grp_key, midi_pedal_conf_menu):
        midi_pedal_conf_menu.add_child(midi_pedal_conf_grp_key, self.show_midi_pedal_config_group_opts,
                                       self.execute_midi_pedal_opt)

    def show_midi_pedal_config_group_opts(self):
        midi_pedal_name = self.midi_pedal_menu.children[self.midi_pedal_menu.current_child].name
        current_pedal_config = self.midi_pedal_config_menu[midi_pedal_name]
        config_option_group_name = current_pedal_config.children[current_pedal_config.current_child].name
        current_midi_pedal_config_opt_menu = self.midi_pedal_config_menu[midi_pedal_name].children[
            self.midi_pedal_config_menu[midi_pedal_name].current_child]
        current_midi_pedal_config_opt_menu.menu_data_items = []
        current_midi_pedal_config_opt_menu.menu_data_prompt = current_midi_pedal_config_opt_menu.name + ":"
        current_midi_pedal_config_opt_menu.menu_data_position = self.menu_data_item_position_init(
            current_midi_pedal_config_opt_menu.menu_data_position)
        midi_pedal_conf_opt = self.midi_pedal_dict[midi_pedal_name].midi_pedal_conf_dict.get(config_option_group_name,
                                                                                             None)
        if midi_pedal_conf_opt:
            if config_option_group_name in ["Knobs/Switches", "Parameters"]:
                for midi_pedal_conf_opt_key, midi_pedal_conf_opt_value in midi_pedal_conf_opt.iteritems():
                    if midi_pedal_conf_opt_value:
                        current_midi_pedal_config_opt_menu.menu_data_items.append(midi_pedal_conf_opt_key)
                        current_midi_pedal_config_opt_menu.menu_data_dict.update(
                            {midi_pedal_conf_opt_key: midi_pedal_conf_opt_value})
                        self.set_midi_pedal_conf_opts_menu(midi_pedal_conf_opt_key, current_midi_pedal_config_opt_menu)
                self.test_point_node_printer(current_midi_pedal_config_opt_menu)
            elif config_option_group_name in ["Engage", "Bypass", "Toggle Bypass"]:
                current_midi_pedal_config_opt_menu.menu_data_dict.update(midi_pedal_conf_opt)
                self.execute_midi_pedal_opt()
            elif config_option_group_name in ["Set Preset", "Set Tempo"]:
                self.parse_option_dict(midi_pedal_conf_opt)
        else:
            logger.warn("No dictionary found for this group: " + config_option_group_name)

    def set_midi_pedal_conf_opts_menu(self, midi_pedal_conf_opt_key, midi_pedal_opt_menu):
        midi_pedal_opt_menu.add_child(midi_pedal_conf_opt_key, self.show_midi_pedal_config_group_opt_details,
                                      self.execute_midi_pedal_group_opt)

    def show_midi_pedal_config_group_opt_details(self):
        self.menu.current_node.menu_data_items = []
        self.menu.current_node.menu_data_prompt = self.menu.current_node.name + ":"
        self.menu.current_node.menu_data_position = self.menu_data_item_position_init(
            self.menu.current_node.menu_data_position)
        midi_pedal_conf_group_opt_dict = self.menu.current_node.parent.menu_data_dict.get(
            self.menu.current_node.name, None)
        if midi_pedal_conf_group_opt_dict:
            self.parse_option_dict(midi_pedal_conf_group_opt_dict)

    def parse_option_dict(self, midi_pedal_opt_dict):
        if any([k in midi_pedal_opt_dict for k in self.leaf_keys]):
            min_val = midi_pedal_opt_dict.get("min", None)
            max_val = midi_pedal_opt_dict.get("max", None)
            cc = midi_pedal_opt_dict.get("cc", None)
            pc = midi_pedal_opt_dict.get("pc", None)
            program_change = midi_pedal_opt_dict.get("program change", None)
            control_change = midi_pedal_opt_dict.get("control change", None)
            multi = midi_pedal_opt_dict.get("multi", None)
            val = midi_pedal_opt_dict.get("value", None)
            on = midi_pedal_opt_dict.get("on", None)
            off = midi_pedal_opt_dict.get("off", None)
            opt_dict = midi_pedal_opt_dict.get("dict", None)
            press = midi_pedal_opt_dict.get("press", None)
            release = midi_pedal_opt_dict.get("release", None)
            if any(x is not None for x in [cc, pc, program_change, multi]):
                if None not in [min_val, max_val]:
                    logger.info("Display min and max so user can choose value: \
                            (" + str(min_val) + ", " + str(max_val) + ").")
                    self.menu.current_node.menu_data_items = range(min_val, max_val + 1)
                elif None not in [on, off]:
                    logger.info("Display off and on so user can choose value: (off: " + str(off) + ", on: " + str(
                        on) + ").")
                    self.menu.current_node.menu_data_items = ['off', 'on']
                elif None not in [press, release]:
                    logger.info("Display press and release so user can choose value: (press: " + str(
                        press) + ", release: " + str(release) + ").")
                    self.menu.current_node.menu_data_items = ['press', 'release']
                elif opt_dict:
                    logger.info("Display press and release so user can choose value: (press: " + str(
                        press) + ", release: " + str(release) + ").")
                    self.menu.current_node.menu_data_items = \
                        [k for k, v in sorted(opt_dict.items(), key=lambda item: item[1])]
                elif val is not None:
                    self.execute_midi_pedal_group_opt()
                else:
                    logger.warn("Cant parse option dictionary.")
            elif control_change is not None:
                control_change_func_dict = control_change.get("func", None)
                if control_change_func_dict is not None:
                    self.menu.current_node.menu_data_items = control_change.get("options", [])
                    # self.execute_midi_pedal_group_opt()
            else:
                logger.warn("Can't execute a midi command without instructions.")
        else:
            for midi_pedal_deeper_conf_opt_key, midi_pedal_deeper_conf_opt_value in \
                    midi_pedal_opt_dict.iteritems():
                if midi_pedal_deeper_conf_opt_value:
                    self.menu.current_node.menu_data_items.append(midi_pedal_deeper_conf_opt_key)
                    self.menu.current_node.menu_data_dict.update(
                        {midi_pedal_deeper_conf_opt_key: midi_pedal_deeper_conf_opt_value})
                    self.set_midi_pedal_conf_opts_menu(midi_pedal_deeper_conf_opt_key, self.menu.current_node)
            self.test_point_node_printer(self.menu.current_node)

    @staticmethod
    def menu_data_item_position_init(current_value):
        return 0 if current_value is None else current_value

    # def show_bpm(self):
    #     self.bpm_menu.menu_data_prompt = self.bpm_menu.name + ":"
    #     self.bpm_menu.menu_data_items = self.tempo_range
    #     # tempo range starts at 40 and goes to 500 by 0.5
    #     logger.info("bpm: " + self.current_song.data.bpm)
    #     logger.info("position in list: " + str(self.bpm_menu.menu_data_position))
    #     self.bpm_menu.menu_data_position = int(2 * (float(self.current_song.data.bpm) - 40))
    #     self.test_point_node_printer(self.midi_pedal_config_menu)

    def load_set_func(self):
        self.set_message("Loading set...")
        self.setlist_name = self.setlist_menu.menu_data_items[self.setlist_menu.menu_data_position]
        self.setlist.load_setlist(SET_FOLDER + self.setlist_name)
        logger.info("switched current setlist to: " + self.setlist_name + "\n" +
                    "switched current song to: " + str(self.current_song.data.name) + str(self.current_song) + "\n" +
                    "switched current part to: " + str(self.current_part.data.part_name) + str(self.current_part))
        self.current_song = self.setlist.songs.head
        self.current_part = self.current_song.data.parts.head
        self.songs_menu.menu_data_position = self.menu_data_item_position_init(self.songs_menu.menu_data_position)
        self.parts_menu.menu_data_position = self.menu_data_item_position_init(self.parts_menu.menu_data_position)
        self.displayed_song = self.current_song
        self.displayed_part = self.current_part
        self.displayed_song_index = self.setlist.songs.node_to_index(self.displayed_song)
        self.displayed_part_index = self.current_song.data.parts.node_to_index(self.displayed_part)
        self.load_part()
        self.change_menu_nodes()

    def load_song_func(self):
        self.current_song = self.setlist.songs.index_to_node(self.songs_menu.menu_data_position + 1)
        self.load_song()
        self.change_menu_nodes()

    def load_part_func(self):
        self.current_part = self.current_song.data.parts.index_to_node(self.parts_menu.menu_data_position + 1)
        self.load_part()
        self.change_menu_nodes()

    def load_midi_pedal_config_menu(self):
        midi_pedal_name = self.midi_pedal_menu.children[self.midi_pedal_menu.current_child].name
        midi_pedal_config = self.midi_pedal_config_menu[midi_pedal_name].menu_data_items[
            self.midi_pedal_config_menu[midi_pedal_name].menu_data_position]
        self.set_message(midi_pedal_config)

    def execute_midi_pedal_opt(self):
        midi_pedal_name = self.midi_pedal_menu.children[self.midi_pedal_menu.current_child].name
        midi_pedal_conf_group_name = self.midi_pedal_config_menu[midi_pedal_name].children[
            self.midi_pedal_config_menu[midi_pedal_name].current_child].name
        current_midi_pedal_option_dict = self.midi_pedal_config_menu[midi_pedal_name].menu_data_dict.get(
            midi_pedal_conf_group_name, None)
        if current_midi_pedal_option_dict:
            logger.info("Executing " + midi_pedal_conf_group_name + " function for " + midi_pedal_name + ".")
            midi_pedal = self.midi_pedal_dict[midi_pedal_name]
            action_dict = midi_pedal.midi_pedal_conf_dict.get(midi_pedal_conf_group_name, {})
            if action_dict:
                if len(self.menu.current_node.menu_data_items) > self.menu.current_node.menu_data_position:
                    action_value = self.menu.current_node.menu_data_items[self.menu.current_node.menu_data_position]
                    midi_pedal.determine_action_method(action_dict, action_value)
                else:
                    midi_pedal.determine_action_method(action_dict)
        else:
            logger.warn(
                "NOT executing " + midi_pedal_conf_group_name + " function for " + midi_pedal_name +
                " as there are no execution parameters given.")
        self.change_menu_nodes(self.menu.current_node.parent)

    def execute_midi_pedal_group_opt(self):
        midi_pedal_name = self.midi_pedal_menu.children[self.midi_pedal_menu.current_child].name
        midi_pedal_conf_group_opt_menu = self.midi_pedal_config_menu[midi_pedal_name].children[
            self.midi_pedal_config_menu[midi_pedal_name].current_child]
        midi_pedal_conf_group_opt_name = midi_pedal_conf_group_opt_menu.children[
            midi_pedal_conf_group_opt_menu.current_child].name
        current_midi_pedal_group_option_dict = midi_pedal_conf_group_opt_menu.menu_data_dict.get(
            midi_pedal_conf_group_opt_name, None)
        if current_midi_pedal_group_option_dict:
            logger.info("Executing " + midi_pedal_conf_group_opt_name + " function for " + midi_pedal_name + ".")
            selected_value = None
            if self.menu.current_node.menu_data_items:
                selected_value = self.menu.current_node.menu_data_items[self.menu.current_node.menu_data_position]
            self.make_midi_pedal_parameter_change(midi_pedal_conf_group_opt_name, selected_value)
        else:
            logger.warn(
                "NOT executing " + midi_pedal_conf_group_opt_name + " function for " + midi_pedal_name +
                " as there are no execution parameters given.")
        self.change_menu_nodes(self.menu.current_node.parent)

    def make_midi_pedal_parameter_change(self, option, value=None):
        midi_pedal_name = self.midi_pedal_menu.children[self.midi_pedal_menu.current_child].name
        self.midi_pedal_dict[midi_pedal_name].set_params({option: value})

    # def load_bpm_func(self):
    #     self.current_song.data.bpm = str(self.bpm_menu.menu_data_items[self.bpm_menu.menu_data_position])
    #     for midi_pedal_obj in self.all_midi_pedals:
    #         if midi_pedal_obj.name is "TapTempo":
    #             midi_pedal_obj.setTempo(float(self.current_song.data.bpm))
    #     self.change_menu_nodes(self.menu.current_node.parent)

    def change_and_select(self, func_name):
        func_dict = {
            "Select Song Dn": self.prev_song,
            "Select Song Up": self.next_song,
            "Select Part Dn": self.prev_part,
            "Select Part Up": self.next_part,
        }
        func = func_dict.get(func_name, None)
        if func:
            func()
            self.select_choice()

    def load_part(self):
        logger.info(
            "switching current part to: " + str(self.current_part.data.part_name) + ": " + str(self.current_part))
        tempo_obj = None
        self.displayed_part_index = self.current_song.data.parts.node_to_index(self.current_part)
        for midi_pedal_obj in self.all_midi_pedals:
            if midi_pedal_obj.name == "TapTempo":
                tempo_obj = midi_pedal_obj  # store this object for later use.
            else:
                state, preset, params, settings = self.current_part.data.pedal_dictionary[midi_pedal_obj.name]
                if state:
                    midi_pedal_obj.turn_on()
                else:
                    midi_pedal_obj.turn_off()
                if preset is not None:
                    midi_pedal_obj.set_preset(preset)
                if params:
                    midi_pedal_obj.set_params(params)
                if settings:
                    midi_pedal_obj.set_setting(settings)

            # if midi_pedal_obj.name == "TimeLine":
            # 	midi_pedal_obj.setTempo(float(self.current_song.data.bpm))
            # need to get all the midi_pedals to their correct state before messing with tempo
        # now that we are out of the for loop, set the tempo
        self.rebuild_menu()
        self.set_song_info_message()
        if tempo_obj is not None:
            tempo_obj.setTempo(float(self.current_song.data.bpm))
        self.save_part_to_default()

    def get_rotary_movement(self, a, b):
        """ accepts pins a and b from rpi gpio, determines the direction of the movement, and returns CW or CCW """
        move = None  # initialize move to None
        seq = b * 2 + a * 1 | b << 1
        logger.info("sequence: " + str(seq))
        if seq in [1, 3]:
            self.last_good_seq = seq
        elif seq == 2:
            if self.last_good_seq == 1:
                move = "CW"
                if self.last_move is not move:
                    self.last_move = move
                    move = "CCW"
            elif self.last_good_seq == 3:
                move = "CCW"
                if self.last_move is not move:
                    self.last_move = move
                    move = "CW"
        return move

    def load_song(self):
        self.current_song = self.displayed_song
        self.current_part = self.displayed_part
        logger.info("switching current song to: " + str(self.current_song.data.name) + ": " + str(self.current_song))
        self.displayed_song_index = self.setlist.songs.node_to_index(self.current_song)
        self.load_part()

    def change_menu_pos(self, direction):
        """ change the current position of the menu and display the new menu item unless the end or the beginning of
        the list has been reached """
        logger.info("direction: " + direction)
        if self.menu.current_node is not self.menu.root:
            if self.menu.current_node.children:
                if direction == "CW":
                    if self.menu.current_node.current_child < len(self.menu.current_node.children) - 1:
                        self.menu.current_node.current_child += 1
                        self.set_children_message()
                elif direction == "CCW":
                    if self.menu.current_node.current_child > 0:
                        self.menu.current_node.current_child -= 1
                        self.set_children_message()
                try:
                    logger.info(
                        "current node name: " + self.menu.current_node.name + ",\nnumber of children in node: " +
                        str(len(self.menu.current_node.children)) + ",\ncurrent child in node: " +
                        str(self.menu.current_node.current_child))
                except Exception as e:
                    logger.exception(e)
                    # logger.info(sys.exc_info()[0])
                    logger.info("current node name: " + self.menu.current_node.name + ",\ncurrent child in node: " +
                                str(self.menu.current_node.current_child))
            else:
                if direction == "CW":
                    self.next_menu_list_item()
                elif direction == "CCW":
                    self.prev_menu_list_item()
                try:
                    logger.info("current node name: " + self.menu.current_node.name + ",\nnumber of elems in list: " +
                                str(len(self.menu.current_node.menu_data_items)) + ",\ncurrent elem in list: " +
                                str(self.menu.current_node.menu_data_position))
                except Exception as e:
                    logger.exception(e)
                    # logger.info(sys.exc_info()[0])
                    logger.info("current node name: " + self.menu.current_node.name + ",\ncurrent elem in list: " +
                                str(self.menu.current_node.menu_data_items[self.menu.current_node.menu_data_position]))

        # TODO: don't let the tempo go below 40 or above 500
        # if tap tempo button is pressed,
        # 	change the tempo by 5
        # else
        # 	change the tempo by 0.5
        else:
            if direction == "CW":
                pass  # TODO: something here
            elif direction == "CCW":
                pass  # TODO: something here

    def get_main_menu_message(self, menu_str):
        if menu_str == "Set":
            self.set_message(self.setlist.setlist_name)
        elif menu_str == "SongInfo":
            self.set_song_info_message()
        elif menu_str == "Song":
            self.display_word_wrap(self.current_song.data.name)
        elif menu_str == "Part":
            self.set_message(self.current_part.data.part_name)
        else:
            self.set_message(self.current_song.data.bpm + "BPM")

    # def getMenuItemString(self):
    # 	"""get the current menu item from the menulist associated with the currentmenu
    # 	"""
    # 	if self.currentMenu == "PartMenu":
    # 		return self.current_part.data.part_name
    # 	if self.currentMenu == "SongMenu":
    # 		return self.current_song.data.name
    # 	else:
    # 		return self.menuDictionary[self.currentMenu][self.menu_data_position]

    def set_message(self, msg):
        """ display a message on the lcd screen """
        self.oled.set_display_message(msg)
        # self.lcd.clear()
        # self.lcd.message(msg)
        self.displayed_msg = msg

    def display_word_wrap(self, text):
        if len(text) > 16:
            overflow = len(text) - 16
            self.set_message(text[:-overflow] + " - " + text[-overflow:])
        else:
            self.set_message(text)

    def set_song_info_message(self):
        self.set_message(self.current_song.data.name + " - "
                         + self.current_song.data.bpm + "BPM - " + self.current_part.data.part_name)
        logger.info("Now displaying indices song: " + str(self.displayed_song_index) + "; part: " + str(
            self.displayed_part_index))

    def set_song_info_message_by_value(self, song, part):
        self.set_message(song.data.name + " - " + song.data.bpm + "BPM - " + part.data.part_name)
        logger.info("Now displaying indices song: " + str(self.displayed_song_index) + "; part: " + str(
            self.displayed_part_index))

    def get_message(self):
        """ return the message on the lcd screen """
        return self.displayed_msg

    def get_current_menu(self):
        """ return the current menu  """
        return self.menu.current_node.name

    def set_midi_pedal_list(self, midi_pedals, mode):
        """ sets the midi_pedal list for the current midi_pedal setup. midi_pedals come in as a dictionary.
        "all_midi_pedals" is a list of the objects from the midi_pedals dictionary but stripped of their
        respective channel numbers. """

        self.all_midi_pedals = midi_pedals.values()
        for midi_pedal_obj in self.all_midi_pedals:
            if isinstance(midi_pedal_obj, EffectLoops.MidiPedal):
                self.midi_pedal_dict[midi_pedal_obj.name] = midi_pedal_obj
        if mode == "favorite":
            self.change_to_footswitch_item()
            self.load_part()
        self.switch_modes(mode)

    def get_midi_pedals_list(self):
        """ returns the midi_pedal list for the current midi_pedal layout """
        return self.all_midi_pedals

    def set_temp_message(self, temp_message):
        saved_message = self.get_message()
        self.set_message(temp_message)
        self.oled._delay_microseconds(1000000)
        # self.lcd._delay_microseconds(1000000)
        self.set_message(saved_message)

    def save_color_as_default(self):
        defaults = self.read_config()
        defaults['knob'].update({
            'color': self.color,
            'brightness': str(self.brightness)
        })
        self.write_config(defaults)

    def save_part_to_default(self):
        defaults = self.read_config()
        defaults['current_settings']['preset'].update({
            'setList': self.setlist_name,
            'song': self.current_song.data.name,
            'part': self.current_part.data.part_name
        })
        self.write_config(defaults)

    def button_executor(self, action):
        if action:
            actions = {
                "Song Dn": self.prev_song,
                "Song Up": self.next_song,
                "Part Dn": self.prev_part,
                "Select": self.select_choice,
                "Part Up": self.next_part
            }
            actions.get(action, self.action_missing)()

    @staticmethod
    def action_missing():
        logger.info("This buttons action does not exist in the actions dictionary.")

    def change_to_footswitch_item(self, button=None):
        if button:
            if button <= self.current_song.data.parts.get_length() and \
                    not self.current_part == self.current_song.data.parts.index_to_node(
                        button):
                self.current_part = self.current_song.data.parts.index_to_node(button)
                self.load_part()

    @staticmethod
    def start_thread(func_thread):
        thread = func_thread
        thread.start()

    def prev_part(self):
        logger.info("This is the \'previous part\' action.")
        self.displayed_part = self.displayed_song.data.parts.index_to_node(self.displayed_part_index - 1)
        if self.displayed_part and (self.displayed_part_index > 1):
            self.displaying_current_songpart = False
            self.start_new_thread()
            self.displayed_part_index -= 1
            self.set_song_info_message_by_value(self.displayed_song, self.displayed_part)
        # TODO: set a timer so the menu changes back to current part after expiration

    def next_part(self):
        logger.info("This is the \'next part\' action.")
        self.displayed_part = self.displayed_song.data.parts.index_to_node(self.displayed_part_index + 1)
        if self.displayed_part and (self.displayed_part_index < self.displayed_song.data.parts.length):
            self.displaying_current_songpart = False
            self.start_new_thread()
            self.displayed_part_index += 1
            self.set_song_info_message_by_value(self.displayed_song, self.displayed_part)
        # TODO: set a timer so the menu changes back to current part after expiration

    def prev_song(self):
        logger.info("This is the \'previous song\' action.")
        self.displayed_song = self.setlist.songs.index_to_node(self.displayed_song_index - 1)
        if self.displayed_song and (self.displayed_song_index > 1):
            self.displaying_current_songpart = False
            self.start_new_thread()
            self.displayed_song_index -= 1
            self.displayed_part_index = 1
            self.displayed_part = self.displayed_song.data.parts.head
            self.set_song_info_message_by_value(self.displayed_song, self.displayed_song.data.parts.head)
        # TODO: set a timer so the menu changes back to current song after expiration

    def start_new_thread(self):
        if not self.check_for_running_threads():
            new_thread = PulsateRgbKnobThread(1, "Pulsate-Thread", self)
            self.start_thread(new_thread)
            self.rotary_threads.append(new_thread)

    def check_for_running_threads(self):
        running_rotary_threads = [thread for thread in self.rotary_threads if thread.isAlive()]
        self.rotary_threads = running_rotary_threads
        return True if len(self.rotary_threads) > 0 else False

    def next_song(self):
        logger.info("This is the \'next song\' action.")
        self.displayed_song = self.setlist.songs.index_to_node(self.displayed_song_index + 1)
        if self.displayed_song and (self.displayed_song_index < self.setlist.songs.length):
            self.displaying_current_songpart = False
            self.start_new_thread()
            self.displayed_song_index += 1
            self.displayed_part_index = 1
            self.displayed_part = self.displayed_song.data.parts.head
            self.set_song_info_message_by_value(self.displayed_song, self.displayed_song.data.parts.head)
        # TODO: set a timer so the menu changes back to current song after expiration

    def select_choice(self):
        logger.info("This is the \'select\' action.")
        self.displaying_current_songpart = True
        if self.current_song is not self.displayed_song:
            # self.current_song = self.displayed_song
            self.load_song()
        elif self.current_part is not self.displayed_part:
            self.current_part = self.displayed_part
            self.load_part()

    def next_menu_list_item(self):
        if self.menu.current_node.menu_data_position < len(self.menu.current_node.menu_data_items) - 1:
            self.menu.current_node.menu_data_position += 1
            # self.menu.current_node.menu_data_items[self.menu.current_node.menu_data_position]
            self.set_menu_data_message()

    def prev_menu_list_item(self):
        if self.menu.current_node.menu_data_position > 0:
            self.menu.current_node.menu_data_position -= 1
            # self.menu.current_node.menu_data_items[self.menu.current_node.menu_data_position]
            self.set_menu_data_message()

    def set_children_message(self):
        if self.menu.current_node.parent not in [None, self.menu.root]:
            display_message = self.menu.current_node.parent.name + ": - " + self.menu.current_node.name + ": - " \
                              + self.menu.current_node.children[self.menu.current_node.current_child].name
        else:
            display_message = self.menu.current_node.name + ": - " \
                              + self.menu.current_node.children[self.menu.current_node.current_child].name
        self.set_message(display_message)

    def set_menu_data_message(self):
        if self.menu.current_node.parent not in [None, self.menu.root]:
            if self.menu.current_node.parent.parent not in [None, self.menu.root]:
                self.set_grandparent_parent_child_grandchild_menu_data_message()
            else:
                self.set_parent_child_grandchild_menu_data_message()
        else:
            self.set_child_grandchild_menu_data_message()

    def set_child_grandchild_menu_data_message(self):
        if self.menu.current_node.menu_data_items:
            self.prepare_for_displaying_message()
            self.set_message(self.menu.current_node.menu_data_prompt + " - " + str(
                self.menu.current_node.menu_data_items[self.menu.current_node.menu_data_position]))

    def set_parent_child_grandchild_menu_data_message(self):
        if self.menu.current_node.menu_data_items:
            self.prepare_for_displaying_message()
            self.set_message(
                self.menu.current_node.parent.name + ": - " + self.menu.current_node.menu_data_prompt + " - " +
                str(self.menu.current_node.menu_data_items[self.menu.current_node.menu_data_position]))

    def set_grandparent_parent_child_grandchild_menu_data_message(self):
        if self.menu.current_node.menu_data_items:
            self.prepare_for_displaying_message()
            self.set_message(self.menu.current_node.parent.parent.name + ": - " + self.menu.current_node.parent.name +
                             ": - " + self.menu.current_node.menu_data_prompt + " - " +
                             str(self.menu.current_node.menu_data_items[self.menu.current_node.menu_data_position]))

    def prepare_for_displaying_message(self):
        self.menu.current_node.menu_data_position = self.menu_data_item_position_init(
            self.menu.current_node.menu_data_position)
        self.test_point_node_printer(self.menu.current_node)

    def change_menu_nodes(self, menu_node=None):
        if menu_node is None:
            menu_node = self.menu.root

        self.menu.current_node = menu_node
        if self.menu.current_node is self.menu.root:
            self.set_song_info_message()
        elif self.menu.current_node.children:
            self.set_children_message()
        elif self.menu.current_node.func:
            logger.info(self.menu.current_node.name + ": menu_func")
            self.menu.current_node.func()
            if self.menu.current_node.children:
                self.set_children_message()
            else:
                self.set_menu_data_message()
            self.menu.current_node.menu_data_loaded = True
        else:
            logger.error("Error!!")
            self.set_message("Error!!")


class RotaryPushButton(EffectLoops.ButtonOnPedalBoard, RotaryEncoder):
    """ class to handle button pushes on the rotary encoder knob. its parents are 'ButtonOnPedalBoard' from the
    'EffectLoops' package and ': "' """

    def __init__(self, button, mode, **kwargs):
        # type = "RotaryPushButton"
        # func_two_type = "Settings"
        # func_two_port = "None"
        self.mode = mode
        name = "RotaryPB"
        RotaryEncoder.__init__(self, **kwargs)  # initialize parent class rotary encoder
        # initialize parent class ButtonOnPedalBoard
        super(RotaryPushButton, self).__init__(name, None, None, button)

    def switch_modes(self, mode=None):
        if mode:
            if mode in ["favorite", "standard"]:
                self.mode = mode
                logger.info(str(mode) + " --> Mode switched to " + self.mode + " mode.")
            else:
                self.mode = "standard"
                logger.info("Did not understand input mode: " + str(mode) + ". Mode will be " + self.mode + " mode.")
        else:
            if self.mode == "favorite":
                self.mode = "standard"
            elif self.mode == "standard":
                self.mode = "favorite"
            logger.info("Mode switched to " + self.mode + " mode.")
        self.save_mode_to_default()

    @staticmethod
    def write_config(config_dict):
        # write to config yaml file from dictionaries
        with open(CONFIG_FILE, 'w') as ymlfile:
            yaml.dump(config_dict, ymlfile)

    @staticmethod
    def read_config():
        # read config yaml file into dictionaries
        with open(CONFIG_FILE, 'r') as ymlfile:
            config_file = yaml.full_load(ymlfile)
        return config_file

    def save_mode_to_default(self):
        defaults = self.read_config()
        defaults['current_settings'].update({
            'mode': self.mode
        })
        self.write_config(defaults)

    def button_state(self, int_capture_pin_val):
        """ sets the state (is_pressed) of the rotaryPushButton and captures the time of the press so that when it is
        released, the difference can be calculated """
        if not int_capture_pin_val:  # when the button was pressed
            self.is_pressed = True
            self.start = time.time()
        else:  # on button release
            self.end = time.time()
            delta_t = self.end - self.start

            if delta_t < 0.5:  # if the press was shorter than half a second
                # select the item or go into the menu currently on the display
                if self.menu.current_node is self.menu.root:
                    logger.info(self.menu.current_node.name + ": main -> setup")
                    self.change_menu_nodes(self.setup_menu)
                elif self.menu.current_node.children:
                    logger.info(self.menu.current_node.name + ": deeper menu")
                    self.change_menu_nodes(self.menu.current_node.children[self.menu.current_node.current_child])
                    if self.menu.current_node.current_child is None:
                        self.menu.current_node.current_child = 0
                elif self.menu.current_node.menu_data_items:
                    if self.menu.current_node.menu_data_func:
                        logger.info(self.menu.current_node.name + ": data_func")
                        self.menu.current_node.menu_data_func()
                        self.menu.current_node.menu_data_loaded = False
                    else:
                        logger.info(self.menu.current_node.name + ": data_items")
                        self.menu.current_node.menu_data_dict[
                            self.menu.current_node.menu_data_items[self.menu.current_node.menu_data_position]]()
            elif delta_t < 2:  # longer than half a second but shorter than 2 seconds
                if self.menu.current_node.parent:
                    logger.info(self.menu.current_node.name + ": child menu -> parent")
                    self.change_menu_nodes(self.menu.current_node.parent)
            else:
                if delta_t > 5:  # if button held for more than 5 seconds
                    if self.menu.current_node is not self.power_menu:
                        logger.info(self.menu.current_node.name + ": ? -> power menu")
                        self.change_menu_nodes(self.power_menu)
                elif self.menu.current_node is self.menu.root:  # if the button was pressed between 2 and 5 secs
                    logger.info(self.menu.current_node.name + ": ? -> global menu")
                    self.change_menu_nodes(self.global_menu)  # if the currentmenu is mainmenu swap to 'Global'
                else:
                    logger.info(self.menu.current_node.name + ": ? -> MidiController main menu")
                    self.change_menu_nodes(self.menu.root)

            self.is_pressed = False  # was released


class PulsateRgbKnobThread(threading.Thread):

    def __init__(self, thread_id, name, rgb_knob):
        threading.Thread.__init__(self)
        self.thread_id = thread_id
        self.name = name
        self.rgb_knob = rgb_knob

    def run(self):
        logger.info("Starting " + self.name)
        self.rgb_knob.pulsate()
        logger.info("Exiting " + self.name)
