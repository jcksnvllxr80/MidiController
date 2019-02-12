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

SET_FOLDER = "/home/pi/Looper/PartSongSet/Sets/"
DEFAULT_FILE = "/home/pi/Looper/Main/PedalGroup.xml"
FONT_FOLDER = '/home/pi/Looper/test/Font/'

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
		self.initPWM() #initalize GPIO for PWM
		self.setColor(col, val) #starting color
		self.startPWM() #start the PWM
		
	def initPWM(self):
		#set the mode for how the GPIO pins will be numbered
		GPIO.setmode(GPIO.BCM)
		#set the list of pin numbers as outputs
		GPIO.setup([self.RED_PIN, self.GREEN_PIN, self.BLUE_PIN], GPIO.OUT)
		#set freq and pin number to a PWM object for each of the 3 RGB components
		self._red = GPIO.PWM(self.RED_PIN, self.FREQ)
		self._green = GPIO.PWM(self.GREEN_PIN, self.FREQ)
		self._blue = GPIO.PWM(self.BLUE_PIN, self.FREQ)
		
	def startPWM(self):
		'''start PWM with (100 - x) dutyCycle
		'''
		self._red.start(100 - self.r)
		self._green.start(100 - self.g)
		self._blue.start(100 - self.b)
	
	def stopPWM(self):
		'''stop the PWM
		'''
		self._red.stop()
		self._green.stop()
		self._blue.stop()
		GPIO.cleanup()
	
	def setBrightness(self, v):
		''' change the global brightness variable and apply to the current color
		'''
		self.brightness = v
		self.setColor(self.color)
		
	def setColor(self, color, v=None):
		''' changes the color of the rotary encoder knob
		'''
		newColor = color
		self.color = newColor
		if v is not None:
			self.brightness = v
		else:
			v = self.brightness
		#depending on the color string set the individual components r, g, and b
		if newColor == self.COLORS[0]:
			self.r, self.g, self.b = (0, 0, 0)
		elif newColor == self.COLORS[1]:
			self.r, self.g, self.b = (0, 0, v)
		elif newColor == self.COLORS[2]:
			self.r, self.g, self.b = (0, v, 0)
		elif newColor == self.COLORS[3]:
			self.r, self.g, self.b = (0, v, v)
		elif newColor == self.COLORS[4]:
			self.r, self.g, self.b = (v, 0, 0)
		elif newColor == self.COLORS[5]:
			self.r, self.g, self.b = (v, 0, v)
		elif newColor == self.COLORS[6]:
			self.r, self.g, self.b = (v, v, 0)
		elif newColor == self.COLORS[7]:
			self.r, self.g, self.b = (v, v, v)	
		#update the duty cycle since duty cycle is how brightness is realized
		self.setRGBDutyCycle()
		
	def setRGBDutyCycle(self):
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
	setup_menu = menu.root.add_child("Setup")
	global_menu = menu.root.add_child("Global")
	
	def __init__(self, **kwargs):		
		knobCol = kwargs["kc"]
		knobBright = kwargs["kb"]
		knob_color = (knobCol, knobBright)
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

		self.rebuild_menu()
		self.set_song_info_message()
		self.goodbye_menu = self.menu.root.add_child("Goodbye", self.power_off_prompt)

		# build global menu
		self.knobcolor_menu = self.global_menu.add_child("Knob Color", self.show_knob_colors)
		self.knobbrightness_menu = self.global_menu.add_child("Knob Brightness", self.show_brightness)

		# self.changeToMenu("MainMenu") #starting menu
		#variables for the rotary movement interpretation loop
		self.last_good_seq = 0
		self.lastSeq = 0
		self.rotary_timer = 0
		#keeps time for last rotary turn in seconds
		self.last_rotary_turn = 0
		self.child_num = 0


	def rebuild_menu(self):
		# build setup menu
		self.songs_menu = self.setup_menu.add_child("Songs", self.show_songs)
		self.parts_menu = self.setup_menu.add_child("Parts", self.show_parts_of_song)
		self.bpm_menu = self.setup_menu.add_child("BPM", self.show_bpm_for_song)
		self.pedal_menu = self.setup_menu.add_child("Pedals", self.show_pedal_states)
		self.setlist_menu = self.setup_menu.add_child("Sets", self.show_available_setlists)


	# def update_menu_properties(self, newMenu):
	# 	'''change to a new menu based on the argument passed 'newMenu', redefine menuitems with the
	# 	items associated with the new menu, set the menu  position to 0, and display the menu item 
	# 	at the current postion.
	# 	'''
	# 	self.menu_items = self.menuDictionary[newMenu]
	# 	self.menu_items_position = 0
	# 	if newMenu == "MainMenu":
	# 		self.get_main_menu_message(self.menu_items[self.menu_items_position])
	# 	else:
	# 		self.set_message(self.menu_items[self.menu_items_position])


	def power_off_prompt(self):
		self.menu_items = ["NO yes", "no YES"]
		self.menu_items_position = 0
		self.set_message("Power Off?")


	def show_knob_colors(self):
		self.menu_items = RgbKnob.COLORS
		self.menu_items_position = 0
		self.set_message("Knob color")


	def show_brightness(self):
		# brightness_range = range(0, 100)
		self.set_message(str(self.brightness))


	def show_pedal_states(self):
		self.current_part.pedal_dictionary


	def show_bpm_for_song(self):
		self.current_song.bpm
		# dont let the tempo go below 40 or above 500
		# if tap tempo button is pressed, 
		# 	change the tempo by 5
		# else
		# 	change the tempo by 0.5 


	def show_parts_of_song(self):
		self.current_song.parts


	def show_songs(self):
		self.setlist.songs


	def show_available_setlists(self):
		# read setlist files from folder where they belong
		# display the first item in the list
		setListFiles = os.listdir(SET_FOLDER)
		setlists = []
		for setListFile in setListFiles:
			if setListFile[-4:] == ".xml":
				newSetName = setListFile[:-4]
			setlists.append(newSetName)
		if setlists:
			return setlists
		else:
			return "No setlists"


	def change_pedal_configuration(self, option):
		if option == "Song Down":
			if self.current_song.prev is not None: 
				self.current_song = self.current_song.prev
				self.loadSong()
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
				self.loadSong()
		# elif option == "Main Menu":
		# 	self.changeToMenu("MainMenu")
		elif option == "Switch Mode":
			for pedal_obj in self.all_pedals:
				if pedal_obj.name == "RotaryPB":
					pedal_obj.switch_modes()
		

			
	def load_part(self):
		tempoObj = None
		for pedal_obj in self.all_pedals:
			if pedal_obj.name not in ["Empty", "RotaryPB", "TapTempo"]:
				state, setting = self.current_part.data.pedal_dictionary[pedal_obj.name]
				if state:
					pedal_obj.turnOn()
				else:
					pedal_obj.turnOff()
				if setting is not None:
					pedal_obj.setSetting(setting)
				if pedal_obj.name == "TimeLine":
					pedal_obj.setTempo(float(self.current_song.data.bpm))
			elif pedal_obj.name == "TapTempo":
				tempoObj = pedal_obj #store this object for later use. 
				#need to get all the pedals to their correct state before messsing with tempo
		#now that we are out of the for loop, set the tempo
		self.rebuild_menu()
		self.set_song_info_message()
		if tempoObj is not None:
			tempoObj.setTempo(float(self.current_song.data.bpm))
		self.save_part_to_default()


	def rotary_movement(self, a, b): 
		''' accepts pins a and b from rpi gpio, determines the direction of the movement, and returns
		CW or CCW
		'''
		move = None #initialize move to None
		newState = b*2 +  a*1 | b << 1
		if newState == 2:
			seq = 3
		elif newState == 3:
			seq =2
		else:
			seq = newState
		delta_time = time.time() - self.rotary_timer
		delta = abs(seq - self.lastSeq)
		if delta > 0:
			if seq == 1:
				if delta_time < 0.05 and self.last_good_seq == 3:
					move = "CCW"
				else:
					move = "CW"
					self.last_good_seq = 1
					self.rotary_timer = time.time()
			elif seq == 3:
				if delta_time < 0.05 and self.last_good_seq == 1:
					move = "CW"
				else:    
					move = "CCW"
					self.last_good_seq = 3
					self.rotary_timer = time.time()
			elif seq == 2:
				if self.last_good_seq == 1:
					move = "CW"
				elif self.last_good_seq == 3:
					move = "CCW"
		self.lastSeq = seq
		return move

		
	def get_rotary_movement(self, a, b):
		'''gets direction from rotary knob after making sure that the interrupts arent 
		happening too fast which might indicate false readings
		'''
		direction = self.rotary_movement(a, b)
		if time.time() - self.last_rotary_turn > 0.16: #0.08:
			self.last_rotary_turn = time.time()
			return direction
		else:
			return None


	# def menuFunction(self,func):
	# 	'''do methods needed based on menu option chosen with rotary encoder and push button
	# 	'''
	# 	if func == "Set":
	# 		#change menu list to a list of all sets in the sets folder set the menuposition to 0
	# 		#and display the first item in the list
	# 		# self.currentMenu = "LoadSetMenu"
	# 		# setListFiles = os.listdir(SET_FOLDER)
	# 		# setlists = []
	# 		# for setListFile in setListFiles:
	# 		# 	if setListFile[-4:] == ".xml":
	# 		# 		newSetName = setListFile[:-4]
	# 		# 	setlists.append(newSetName)
	# 		# self.menuDictionary[self.currentMenu] = setlists
	# 		# self.changeToMenu("LoadSetMenu")
	# 	elif func == "Song":
	# 		#change menu list to a list of all songs in the current setlist, add the list to the menuDict
	# 		#for the SongMenu item and change to the 'SongMenu' menu
	# 		self.currentMenu = "SongMenu"
	# 		self.menuDictionary[self.currentMenu] = self.setlist.songs
	# 		self.current_song = self.menuDictionary[self.currentMenu].head
	# 		self.set_message(self.current_song.data.name)
	# 	elif func == "Part":
	# 		self.currentMenu = "PartMenu"
	# 		self.menuDictionary[self.currentMenu] = self.current_song.data.parts
	# 		self.current_part = self.menuDictionary[self.currentMenu].head
	# 		self.set_message(self.current_part.data.part_name)
	# 	elif func == "Pedals":
	# 		#display a list of pedals
	# 		self.currentMenu = "PedalMenu"
	# 		self.menuDictionary[self.currentMenu] = self.all_pedals
	# 		self.menu_items = self.menuDictionary[self.currentMenu]
	# 		self.menu_items_position = 0
	# 		self.set_message(self.menu_items[self.menu_items_position].name + "\n" + str(self.menu_items[self.menu_items_position].getState()))
	# 	elif func == "BPM":
	# 		self.set_message(self.current_song.data.bpm)
	# 	elif func == "Knob Color":
	# 		self.changeToMenu("KnobMenu")
	# 	elif func == "Knob Brightness":
	# 		self.changeToMenu("BrightnessMenu")
	# 	elif func in self.colorMenu:
	# 		self.setColor(func)
	# 		self.save_color_as_default()
	# 		self.changeToMenu("GlobalMenu")
	# 	elif func in self.brightnessMenu:
	# 		self.setBrightness(int(func))
	# 		self.save_color_as_default()
	# 		self.changeToMenu("GlobalMenu")
	# 	elif func == "Power down? \nno YES":
	# 		self.set_message("Goodbye.")
	# 		self.lcd._delay_microseconds(1000000)
	# 		self.lcd.set_backlight(0)
	# 		os.system('shutdown now -h')
	# 	elif func == "Power down? \nNO yes":
	# 		self.changeToMenu("MainMenu")
	# 	elif self.currentMenu == "LoadSetMenu":
	# 		self.set_message("Loading set...")
	# 		self.setlist_name = func
	# 		self.setlist.load_setlist(SET_FOLDER + func)
	# 		self.current_song = self.setlist.songs.head
	# 		self.current_part = self.current_song.data.parts.head
	# 		self.load_part()
	# 		self.changeToMenu("MainMenu")
	# 	elif self.currentMenu == "LoadFontMenu":
	# 		self.changeToMenu("GlobalMenu")
	# 	elif self.currentMenu == "FontSizeMenu":
	# 		self.changeToMenu("GlobalMenu")
	# 	elif self.currentMenu == "PartMenu":
	# 		self.load_part()
	# 		self.changeToMenu("MainMenu")
	# 	elif self.currentMenu == "SongMenu":
	# 		self.loadSong()
	# 		self.changeToMenu("MainMenu")
	# 	elif self.currentMenu == "PedalMenu":
	# 		if self.menu_items[self.menu_items_position].isEngaged:
	# 			self.menu_items[self.menu_items_position].turnOff()
	# 		else:
	# 			self.menu_items[self.menu_items_position].turnOn()
	# 		self.set_message(self.menu_items[self.menu_items_position].name + "\n" + str(self.menu_items[self.menu_items_position].getState()))


	def loadSong(self):
		self.current_part = self.current_song.data.parts.head
		self.load_part()


	def change_menu_pos(self, direction):
		'''change the current position of the menu and display the new menu item
		unless the end or the beginning of the list has been reached
		'''
		if not self.menu.current_node is self.menu.root:
			if self.menu.current_node.children:
				try:
					print("direction: " + direction + ",\ntype: " + str(type(self.menu.current_node.children)) + ",\ncurrent node name: " + self.menu.current_node.name + ",\nnumber of children in node: " + str(len(self.menu.current_node.children)) + ",\ncurrent child in node: " + str(self.child_num))
				except:
					print(sys.exc_info()[0])
					print("direction: " + direction + ",\ntype: " + str(type(self.menu.current_node.children)) + ",\ncurrent node name: " + self.menu.current_node.name + ",\ncurrent child in node: " + str(self.child_num))
				if direction == "CW":
					if self.child_num < len(self.menu.current_node.children) - 1:
						self.child_num += 1
						self.set_message(self.menu.current_node.name + "\n" + self.menu.current_node.children[self.child_num].name)
				elif direction == "CCW":
					if self.child_num > 0:
						self.child_num -= 1
						self.set_message(self.menu.current_node.name + "\n" + self.menu.current_node.children[self.child_num].name)
			else:
				if direction == "CW":
					pass # TODO: somthing here
				elif direction == "CCW":
					pass # TODO: somthing here
		else:
			if direction == "CW":
				pass # TODO: somthing here
			elif direction == "CCW":
				pass # TODO: somthing here

						
	def get_main_menu_message(self, menuStr):
		if menuStr == "Set":
			self.set_message(self.setlist.setlist_name())
		elif menuStr == "SongInfo":
			self.set_song_info_message()
		elif menuStr == "Song":
			self.display_word_wrap(self.current_song.data.name)
		elif menuStr == "Part":
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
	# 		return self.menuDictionary[self.currentMenu][self.menu_items_position]

			
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
			if button <= self.current_song.data.parts.getLength() and not self.current_part == self.current_song.data.parts.indexToNode(button):
				self.current_part = self.current_song.data.parts.indexToNode(button)
				self.load_part()



class RotaryPushButton(EffectLoops.ButtonOnPedalBoard, Rotary_Encoder):
	'''class to handle button pushes on the rotary encoder knob. its parents are 'ButtonOnPedalBoard' from the 'EffectLoops' package
	and 'Rotary_Encoder' 
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
			if self.isEngaged:
				self.turnOff()
				self.mode = "Pedal"
			else:
				self.turnOn()
				self.mode = "Song"
		else:
			if mode == "Pedal":
				self.turnOff()
				self.mode = "Pedal"
			else:
				self.turnOn()
				self.mode = "Song"
		self.save_mode_to_default()
			
			
	def save_mode_to_default(self):
		Defaults = ET.parse(DEFAULT_FILE)
		Root = Defaults.getroot()
		Root.find('mode').text = self.mode 
		Defaults.write(DEFAULT_FILE,encoding="us-ascii", xml_declaration=True)


	def buttonState(self, intCapturePinVal):
		'''sets the state (isPressed) of the rotaryPushButton and captures the time of the press
		so that when it is released, the difference can be calculated
		'''
		if not intCapturePinVal: #when the button was pressed
			self.isPressed = True
			self.start = time.time()
		else: #on button release
			self.end = time.time()
			deltaT = self.end - self.start 
			
			if deltaT < 0.5: #if the press was shorter than half a second
				# select the item or go into the menu currently on the display
				if self.menu.current_node.func: 
					self.menu.current_node.func()
				elif self.menu.current_node is self.menu.root:
					self.menu.current_node = self.setup_menu
				elif self.menu.current_node.children:
					self.menu.current_node = self.menu.current_node.children[self.child_num]
					self.child_num = 0
				# if self.currentMenu == "GoodbyeMenu" and menuItemStr == "Power down? \nNO yes":
				# 	self.changeToMenu("MainMenu")
			elif deltaT < 2: #longer than half a second but shorter than 2 seconds
				if self.menu.current_node.parent:
					self.menu.current_node = self.menu.current_node.parent
			else: 
				if deltaT > 5: # if button held for more than 5 seconds
					if not self.menu.current_node is self.goodbye_menu:
						self.menu.current_node = self.goodbye_menu		
				elif self.menu.current_node is self.menu.root: # if the button was pressed btwn 2 and 5 secs
					self.menu.current_node = self.global_menu # if the currentmenu is mainmenu swap to 'Global'
				else:
					self.menu.current_node = self.menu.root
			self.isPressed = False #was released
