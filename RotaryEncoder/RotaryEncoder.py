#import python packages
import sys
import time
import RPi.GPIO as GPIO
import os
import xml.etree.ElementTree as ET # for reading and writing to XML files
#import custom packages
import EffectLoops
import Adafruit_CharLCD
import PartSongSet
import N_Tree
from numpy import arange
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
formatter = logging.Formatter("%(asctime)s [RotaryEncoder.py] [%(levelname)-5.5s]  %(message)s")
handler.setFormatter(formatter)
logger.addHandler(handler)

SET_FOLDER = "/home/pi/Looper/PartSongSet/Sets/"
DEFAULT_FILE = "/home/pi/Looper/Main/PedalGroup.xml"

#define class for the PWM driver for the colors part of the rotary knob
class RgbKnob(object):
	
	#GPIO pin on rpi
	RED_PIN = 16
	GREEN_PIN = 20
	BLUE_PIN = 21
	#global variables
	FREQ = 1000
	COLORS = ["Off", "Blue", "Green", "Cyan", "Red", "Magenta", "Yellow", "White"]
	
	def __init__(self, knob_color):
		col, val = knob_color
		self.init_pwm() #initalize GPIO for PWM
		self.set_color(col, val) #starting color
		self.start_pwm() #start the PWM
		
	def init_pwm(self):
		#set the mode for how the GPIO pins will be numbered
		GPIO.setmode(GPIO.BCM)
		#set the list of pin numbers as outputs
		GPIO.setup([self.RED_PIN, self.GREEN_PIN, self.BLUE_PIN], GPIO.OUT)
		#set freq and pin number to a PWM object for each of the 3 RGB components
		self._red = GPIO.PWM(self.RED_PIN, self.FREQ)
		self._green = GPIO.PWM(self.GREEN_PIN, self.FREQ)
		self._blue = GPIO.PWM(self.BLUE_PIN, self.FREQ)
		
	def start_pwm(self):
		'''start PWM with (100 - x) dutyCycle
		'''
		self._red.start(100 - self.r)
		self._green.start(100 - self.g)
		self._blue.start(100 - self.b)
	
	def stop_pwm(self):
		'''stop the PWM
		'''
		self._red.stop()
		self._green.stop()
		self._blue.stop()
		GPIO.cleanup()
	
	def set_brightness(self, v):
		''' change the global brightness variable and apply to the current color
		'''
		self.brightness = v
		self.set_color(self.color)
		
	def set_color(self, color, v=None):
		''' changes the color of the rotary encoder knob
		'''
		new_color = color
		self.color = new_color
		if v is not None:
			self.brightness = v
		else:
			v = self.brightness
		#depending on the color string set the individual components r, g, and b
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
		#update the duty cycle since duty cycle is how brightness is realized
		self.set_rgb_duty_cycle()
		
	def set_rgb_duty_cycle(self):
		''' update the duty cycle for each component of RGB
		'''
		self._red.ChangeDutyCycle(100 - self.r)
		self._green.ChangeDutyCycle(100 - self.g)
		self._blue.ChangeDutyCycle(100 - self.b)
	


class Rotary_Encoder(RgbKnob):
	'''class for everything to do with the rotary encoder. its parent is RgbKnob
	'''

	# NOTE: Need to always display song info (main menu / root of menu tree)
	# on 1 short click go to song/set/part/bpm/pedal menun
	# on 2 second click got to global menu
	# on 5 second click go to power off menu

	# build menu with N_Tree
	menu = N_Tree.N_Tree("Looper")
	setup_menu = menu.root.add_child("Setup:")
	global_menu = menu.root.add_child("Global:")
	
	def __init__(self, **kwargs):		
		knob_col = kwargs["kc"]
		knob_bright = kwargs["kb"]
		knob_color = (knob_col, knob_bright)
		previously_loaded_set = kwargs["sl"]
		previously_loaded_song = kwargs["s"]
		previously_loaded_part = kwargs["p"]
		#initialize parent class
		super(Rotary_Encoder, self).__init__(knob_color)
		self.lcd = Adafruit_CharLCD.Adafruit_CharLCDPlate() #Rotary_Encoder "has-a" lcd
		self.setlist = PartSongSet.Setlist() #Rotary_Encoder "has-a" Setlist
		self.displayed_msg = ""
		self.setlist_name = previously_loaded_set
		#load the set, song, and part that was last used that was saved to the default file
		self.setlist.load_setlist(SET_FOLDER + previously_loaded_set)
		self.current_song = self.setlist.songs.head
		while self.current_song.next is not None and previously_loaded_song <> self.current_song.data.name:
			self.current_song = self.current_song.next
		self.current_part = self.current_song.data.parts.head
		while self.current_part.next is not None and previously_loaded_part <> self.current_part.data.part_name:
			self.current_part = self.current_part.next

		# set up the Looper setup menus (set, seong, part, pedal, bpm)
		self.setlist_menu = self.setup_menu.add_child("Sets", self.show_setlists, self.load_set_func)
		self.songs_menu = self.setup_menu.add_child("Songs", self.show_songs, self.load_song_func)
		self.parts_menu = self.setup_menu.add_child("Parts", self.show_parts, self.load_part_func)
		self.pedal_menu = self.setup_menu.add_child("Pedals", self.show_pedals, self.load_pedal_func)
		self.bpm_menu = self.setup_menu.add_child("BPM", self.show_bpm, self.load_bpm_func)
		# dont let the tempo go below 40 or above 500
		self.tempo_range = arange(40,500,0.5).tolist()
		self.set_song_info_message()

		# define power menu
		self.power_menu = self.menu.root.add_child("Power", self.set_menu_data_message)
		self.power_menu.menu_data_prompt = "Power Off?"
		self.power_menu.menu_data_items = ["NO yes", "no YES"]
		self.power_menu.menu_data_dict = {"NO yes": self.change_menu_nodes, "no YES": self.power_off}

		# build global menu
		self.knobcolor_menu = self.global_menu.add_child("Knob Color", self.show_knob_colors, self.load_color_func)
		self.knobbrightness_menu = self.global_menu.add_child("Knob Brightness", self.show_brightness, self.load_brightness_func)

		#variables for the rotary movement interpretation loop
		self.last_good_seq = 0
		self.last_move = None
		
		#keeps time for last rotary turn in seconds
		self.last_rotary_turn = 0
		self.menu.current_node.current_child = 0


	# TODO: this is broken. it should be a way to set the contents of the menu. 
	def rebuild_menu(self):
		# build setup menu based on current files stored in filesystem
		pass


	def power_off(self):
		self.set_message("Goodbye.")
		self.lcd._delay_microseconds(1000000)
		self.lcd.set_backlight(0)
		os.system('sudo shutdown now -h')


	def show_knob_colors(self):
		self.knobcolor_menu.menu_data_items = RgbKnob.COLORS
		self.knobcolor_menu.menu_data_prompt = self.knobcolor_menu.name + ":"
		self.knobcolor_menu.menu_data_position = RgbKnob.COLORS.index(self.color)
		self.test_point_node_printer(self.knobcolor_menu)


	def show_brightness(self):
		self.knobbrightness_menu.menu_data_items = range(0, 101, 10)
		self.knobbrightness_menu.menu_data_prompt = self.knobbrightness_menu.name + ":"
		self.knobbrightness_menu.menu_data_position = self.knobbrightness_menu.menu_data_items.index(self.brightness)
		self.test_point_node_printer(self.knobbrightness_menu)


	def load_color_func(self):
		self.set_color(self.knobcolor_menu.menu_data_items[self.knobcolor_menu.menu_data_position])
		self.save_color_as_default()
		self.change_menu_nodes(self.knobcolor_menu.parent)


	def load_brightness_func(self):
		self.set_brightness(self.knobbrightness_menu.menu_data_items[self.knobbrightness_menu.menu_data_position])
		self.save_color_as_default()
		self.change_menu_nodes(self.knobbrightness_menu.parent)


	def test_point_node_printer(self, the_node):
		pass
		logger.info("\nnode: " + str(the_node) + "prompt: " + the_node.menu_data_prompt + 
			"\nitems: " + str(the_node.menu_data_items) + "\ncurrent item: " + str(the_node.menu_data_items[the_node.menu_data_position]) + 
			"\nposition: " + str(the_node.menu_data_position))


	def show_setlists(self):
		# read setlist files from folder where they belong
		# display the first item in the list
		self.setlist_menu.menu_data_items = []
		self.setlist_menu.menu_data_prompt = self.setlist_menu.name + ":"
		setlist_files = os.listdir(SET_FOLDER)
		for setlist_file in setlist_files:
			if setlist_file[-4:] == ".xml":
				self.setlist_menu.menu_data_items.append(setlist_file[:-4])
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


	def show_pedals(self):
		self.pedal_menu.menu_data_prompt = self.pedal_menu.name + ":"
		self.pedal_menu.menu_data_items = self.all_pedals
		self.pedal_menu.menu_data_position = 0
		self.test_point_node_printer(self.pedal_menu)


	def show_bpm(self):
		self.bpm_menu.menu_data_prompt = self.bpm_menu.name + ":"
		self.bpm_menu.menu_data_items = self.tempo_range
		# tempo range starts at 40 and goes to 500 by 0.5
		logger.info("bpm: " + self.current_song.data.bpm)
		logger.info("position in list: " + str(self.bpm_menu.menu_data_position))
		self.bpm_menu.menu_data_position = int(2 * (float(self.current_song.data.bpm) - 40))
		self.test_point_node_printer(self.bpm_menu)


	def load_set_func(self):
		self.set_message("Loading set...")
		self.setlist_name = self.setlist_menu.menu_data_items[self.setlist_menu.menu_data_position]
		self.setlist.load_setlist(SET_FOLDER + self.setlist_name)
		logger.info("switched current setlist to: " + self.setlist_name + "\n" +
			  "switched current song to: " + str(self.current_song.data.name) + str(self.current_song) + "\n" +
			  "switched current part to: " + str(self.current_part.data.part_name) + str(self.current_part))
		self.current_song = self.setlist.songs.head
		self.current_part = self.current_song.data.parts.head
		self.load_part()
		self.change_menu_nodes()


	def load_song_func(self):
		self.current_song = self.setlist.songs.index_to_node(self.songs_menu.menu_data_position + 1)
		logger.info("switched current song to: " + str(self.current_song.data.name) + str(self.current_song))
		self.load_song()
		self.change_menu_nodes()


	def load_part_func(self):
		self.current_part = self.current_song.data.parts.index_to_node(self.parts_menu.menu_data_position + 1)
		logger.info("switched current part to: " + str(self.current_part.data.part_name) + str(self.current_part))
		self.load_part()
		self.change_menu_nodes()


	def load_pedal_func(self):
		pedal = self.pedal_menu.menu_data_items[self.pedal_menu.menu_data_position]
		if pedal.is_engaged:
			pedal.turn_off()
		else:
			pedal.turn_on()
		self.set_message(pedal.name + "\n" + str(pedal.getState()))


	def load_bpm_func(self):
		self.current_song.data.bpm = str(self.bpm_menu.menu_data_items[self.bpm_menu.menu_data_position])
		for pedal_obj in self.all_pedals:
			if pedal_obj.name is "TapTempo":
				pedal_obj.setTempo(float(self.current_song.data.bpm))

		self.change_menu_nodes(self.menu.current_node.parent)


	def change_pedal_configuration(self, option):
		if option == "Song Down":
			if self.current_song.prev is not None: 
				self.current_song = self.current_song.prev
				self.load_song()
		elif option == "Part Down":
			if self.current_part.prev is not None: 
				self.current_part = self.current_part.prev
				self.load_part()
		elif option == "Part Up":
			if self.current_part.next is not None: 
				self.current_part = self.current_part.next
				self.load_part()
		elif option == "Song Up":
			if self.current_song.next is not None: 
				self.current_song = self.current_song.next
				self.load_song()
		elif option == "Switch Mode":
			for pedal_obj in self.all_pedals:
				if pedal_obj.name == "RotaryPB":
					pedal_obj.switch_modes()
					break
		

			
	def load_part(self):
		tempo_obj = None
		for pedal_obj in self.all_pedals:
			if pedal_obj.name not in ["Empty", "RotaryPB", "TapTempo"]:
				state, setting = self.current_part.data.pedal_dictionary[pedal_obj.name]
				if state:
					pedal_obj.turn_on()
				else:
					pedal_obj.turn_off()
				if setting is not None:
					pedal_obj.set_setting(setting)
				if pedal_obj.name == "TimeLine":
					pedal_obj.setTempo(float(self.current_song.data.bpm))
			elif pedal_obj.name == "TapTempo":
				tempo_obj = pedal_obj #store this object for later use. 
				#need to get all the pedals to their correct state before messsing with tempo
		#now that we are out of the for loop, set the tempo
		self.rebuild_menu()
		self.set_song_info_message()
		if tempo_obj is not None:
			tempo_obj.setTempo(float(self.current_song.data.bpm))
		self.save_part_to_default()

		
	def get_rotary_movement(self, a, b):
		''' accepts pins a and b from rpi gpio, determines the direction of the movement, and returns
		CW or CCW
		'''
		move = None #initialize move to None
		seq = b*2 +  a*1 | b << 1
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
		self.current_part = self.current_song.data.parts.head
		self.load_part()


	def change_menu_pos(self, direction):
		'''change the current position of the menu and display the new menu item
		unless the end or the beginning of the list has been reached
		'''
		logger.info("direction: " + direction)
		if not self.menu.current_node is self.menu.root:
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
					logger.info("current node name: " + self.menu.current_node.name + ",\nnumber of children in node: " + 
						str(len(self.menu.current_node.children)) + ",\ncurrent child in node: " + 
						str(self.menu.current_node.current_child))
				except:
					logger.info(sys.exc_info()[0])
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
				except:
					logger.info(sys.exc_info()[0])
					logger.info("current node name: " + self.menu.current_node.name + ",\ncurrent elem in list: " + 
						str(self.menu.current_node.menu_data_items[self.menu.current_node.menu_data_position]))
		
			# TODO: dont let the tempo go below 40 or above 500
			# if tap tempo button is pressed, 
			# 	change the tempo by 5
			# else
			# 	change the tempo by 0.5 
		else:
			if direction == "CW":
				pass # TODO: somthing here
			elif direction == "CCW":
				pass # TODO: somthing here

						
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
	# 	'''get the current menu item from the menulist associated with the currentmenu
	# 	'''
	# 	if self.currentMenu == "PartMenu":
	# 		return self.current_part.data.part_name
	# 	if self.currentMenu == "SongMenu":
	# 		return self.current_song.data.name
	# 	else:
	# 		return self.menuDictionary[self.currentMenu][self.menu_data_position]

			
	def set_message(self, msg):
		'''display a message on the lcd screen
		'''
		self.lcd.clear()
		self.lcd.message(msg)
		self.displayed_msg = msg

		
	def display_word_wrap(self, text):
		if len(text) > 16:
			overflow = len(text) - 16
			self.set_message(text[:-overflow] + "\n" + text[-overflow:])
		else:
			self.set_message(text)

			
	def set_song_info_message(self):
		self.set_message(self.current_song.data.name + "\n"
			+ self.current_song.data.bpm + "BPM - " + self.current_part.data.part_name)

			
	def get_message(self):
		'''return the message on the lcd screen
		'''
		return self.displayed_msg

		
	def get_current_menu(self):
		'''return the current menu 
		'''
		return self.menu.current_node.name

		
	def set_pedals_list(self, pedals, mode):
		'''sets the pedal list for the current pedal layout.
		pedals come in as a dictionary. "all_pedals" is a list 
		of the objects from the pedals dictionary but stripped 
		of their respective button numbers.
		'''
		self.pedal_button_dict = {}
		self.pedal_pin_dict = pedals
		self.all_pedals = self.pedal_pin_dict.values()
		for pedal_obj in self.all_pedals:
			if isinstance(pedal_obj, EffectLoops.ButtonOnPedalBoard) and pedal_obj.name != "RotaryPB":
				self.pedal_button_dict[pedal_obj.button] = pedal_obj
		if mode == "Song":
			self.change_to_footswitch_item()
			self.load_part()
		self.switch_modes(mode)

		
	def get_pedals_list(self):
		'''returns the pedal list for the current pedal layout
		'''
		return self.all_pedals

		
	def set_temp_message(self, temp_message):
		saved_message = self.get_message()
		self.set_message(temp_message)
		self.lcd._delay_microseconds(1000000)
		self.set_message(saved_message)

		
	def save_color_as_default(self):
		Defaults = ET.parse(DEFAULT_FILE)
		Root = Defaults.getroot()
		Root.find('knobColor').text = self.color 
		Root.find('knobBrightness').text = str(self.brightness) 
		Defaults.write(DEFAULT_FILE,encoding="us-ascii", xml_declaration=True)

		
	def save_part_to_default(self):
		Defaults = ET.parse(DEFAULT_FILE)
		Root = Defaults.getroot()
		Root.find('setList').text = self.setlist_name
		Root.find('song').text = self.current_song.data.name
		Root.find('part').text = self.current_part.data.part_name
		Defaults.write(DEFAULT_FILE,encoding="us-ascii", xml_declaration=True)

	
	def change_to_footswitch_item(self, button=None):
		if button is not None:
			if button <= self.current_song.data.parts.getLength() and not self.current_part == self.current_song.data.parts.index_to_node(button):
				self.current_part = self.current_song.data.parts.index_to_node(button)
				self.load_part()


	def next_menu_list_item(self):
		if self.menu.current_node.menu_data_position < len(self.menu.current_node.menu_data_items) - 1:
			self.menu.current_node.menu_data_position += 1
			self.menu.current_node.menu_data_items[self.menu.current_node.menu_data_position]
			self.set_menu_data_message()


	def prev_menu_list_item(self):
		if self.menu.current_node.menu_data_position > 0:
			self.menu.current_node.menu_data_position -= 1
			self.menu.current_node.menu_data_items[self.menu.current_node.menu_data_position]
			self.set_menu_data_message()


	def set_children_message(self):
		self.set_message(self.menu.current_node.name + "\n" + 
			self.menu.current_node.children[self.menu.current_node.current_child].name)


	def set_menu_data_message(self):
		self.test_point_node_printer(self.menu.current_node)
		self.set_message(self.menu.current_node.menu_data_prompt + "\n" 
			+ str(self.menu.current_node.menu_data_items[self.menu.current_node.menu_data_position]))


	def change_menu_nodes(self, menu_node=None):
		if menu_node is None:
			menu_node = self.menu.root
		
		self.menu.current_node = menu_node
		
		if menu_node is self.menu.root:
			self.set_song_info_message()
		elif self.menu.current_node.children:
			self.set_children_message()
		elif self.menu.current_node.func: 
			logger.info(self.menu.current_node.name + ": menu_func")
			self.menu.current_node.func()
			self.set_menu_data_message()
			self.menu.current_node.menu_data_loaded = True
		else:
			logger.error("Error!!")
			self.set_message("Error!!")


class RotaryPushButton(EffectLoops.ButtonOnPedalBoard, Rotary_Encoder):
	'''class to handle button pushes on the rotary encoder knob. its parents are 'ButtonOnPedalBoard' 
	from the 'EffectLoops' package and 'Rotary_Encoder' 
	'''
	def __init__(self, button, state, mode, **kwargs):
		type = "RotaryPushButton"
		func_two_type = "Settings"
		func_two_port = "None"
		name = "RotaryPB"
		Rotary_Encoder.__init__(self, **kwargs) #initialize parent class rotary encoder
		#initialize parent class buttonOnPedalboard
		super(RotaryPushButton, self).__init__(name, state, button, type, func_two_type, func_two_port)
		
		
	def switch_modes(self, mode=None):
		if mode is None:
			if self.is_engaged:
				self.turn_on()
				self.mode = "Pedal"
			else:
				self.turn_off()
				self.mode = "Song"
		else:
			if mode == "Pedal":
				self.turn_on()
				self.mode = "Pedal"
			else:
				self.turn_off()
				self.mode = "Song"
		logger.info(mode + " --> Mode switched to " + self.mode + " mode.")
		self.save_mode_to_default()
			
			
	def save_mode_to_default(self):
		Defaults = ET.parse(DEFAULT_FILE)
		Root = Defaults.getroot()
		Root.find('mode').text = self.mode 
		Defaults.write(DEFAULT_FILE,encoding="us-ascii", xml_declaration=True)


	def button_state(self, int_capture_pin_val):
		'''sets the state (is_pressed) of the rotaryPushButton and captures the time of the press
		so that when it is released, the difference can be calculated
		'''
		if not int_capture_pin_val: #when the button was pressed
			self.is_pressed = True
			self.start = time.time()
		else: #on button release
			self.end = time.time()
			delta_t = self.end - self.start 
			
			if delta_t < 0.5: #if the press was shorter than half a second
				# select the item or go into the menu currently on the display
				if self.menu.current_node is self.menu.root:
					logger.info(self.menu.current_node.name + ": main -> setup")
					self.change_menu_nodes(self.setup_menu)
				elif self.menu.current_node.children:
					logger.info(self.menu.current_node.name + ": deeper menu")
					self.change_menu_nodes(self.menu.current_node.children[self.menu.current_node.current_child])
					self.menu.current_node.current_child = 0
				elif self.menu.current_node.menu_data_items:
					if self.menu.current_node.menu_data_func:
						logger.info(self.menu.current_node.name + ": data_func")
						self.menu.current_node.menu_data_func()
						self.menu.current_node.menu_data_loaded = False
					else:	
						logger.info(self.menu.current_node.name + ": data_items")
						self.menu.current_node.menu_data_dict[self.menu.current_node.menu_data_items[self.menu.current_node.menu_data_position]]()
			elif delta_t < 2: #longer than half a second but shorter than 2 seconds
				if self.menu.current_node.parent:
					logger.info(self.menu.current_node.name + ": child menu -> parent")
					self.change_menu_nodes(self.menu.current_node.parent)
			else: 
				if delta_t > 5: # if button held for more than 5 seconds
					if not self.menu.current_node is self.power_menu:
						logger.info(self.menu.current_node.name + ": ? -> power menu")
						self.change_menu_nodes(self.power_menu)	
				elif self.menu.current_node is self.menu.root: # if the button was pressed btwn 2 and 5 secs
					logger.info(self.menu.current_node.name + ": ? -> global menu")
					self.change_menu_nodes(self.global_menu) # if the currentmenu is mainmenu swap to 'Global'
				else:
					logger.info(self.menu.current_node.name + ": ? -> Looper main menu")
					self.change_menu_nodes(self.menu.root)

			self.is_pressed = False #was released
