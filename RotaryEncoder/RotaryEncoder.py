#import python packages
import time
import RPi.GPIO as GPIO
import os
import xml.etree.ElementTree as ET # for reading and writing to XML files
#import user packages
import EffectLoops
import Adafruit_CharLCD
import PartSongSet

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
		if newColor == "Off":
			self.r, self.g, self.b = (0, 0, 0)
		elif newColor == "Blue":
			self.r, self.g, self.b = (0, 0, v)
		elif newColor == "Green":
			self.r, self.g, self.b = (0, v, 0)
		elif newColor == "Cyan":
			self.r, self.g, self.b = (0, v, v)
		elif newColor == "Red":
			self.r, self.g, self.b = (v, 0, 0)
		elif newColor == "Magenta":
			self.r, self.g, self.b = (v, 0, v)
		elif newColor == "Yellow":
			self.r, self.g, self.b = (v, v, 0)
		elif newColor == "White":
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
	#menu list definitions
	brightnessMenu = ["0", "1", "7", "15", "30", "50", "100"]
	fontSizeMenu = ["12", "14", "16", "18", "20", "24", "28", "32", "38", "48"]
	colorMenu = ["Off", "Blue", "Green", "Cyan", "Red", "Magenta", "Yellow", "White"]
	#menu definitions
	menuDictionary = {"MainMenu":["SongInfo", "Set", "Song", "Part", "BPM", "Pedals"], 
		"GlobalMenu":["Knob Color", "Knob Brightness", "Font Type", "Font Size"],
		"BrightnessMenu":brightnessMenu, "FontSizeMenu":fontSizeMenu,
		"GoodbyeMenu":["Power down? \nNO yes", "Power down? \nno YES"],
		"KnobMenu":colorMenu, "LoadSetMenu":[], "LoadSongMenu":[], "SongMenu":[],
		"LoadFontMenu":[], "PartMenu":[], "PedalMenu":[]}

	#DefaultPedals = ET.parse(DEFAULT_FILE) 
	#DefaultPedalsRoot = DefaultPedals.getroot() #assign the root of the file to a variable
	
	def __init__(self, **kwargs):
		knobCol = kwargs["kc"]
		knobBright = kwargs["kb"]
		knob_color = (knobCol, knobBright)
		set = kwargs["sl"]
		song = kwargs["s"]
		part = kwargs["p"]
		#initialize parent class
		super(Rotary_Encoder, self).__init__(knob_color)
		self.lcd = Adafruit_CharLCD.Adafruit_CharLCDPlate() #Rotary_Encoder "has-a" lcd
		self.setlist = PartSongSet.Setlist() #Rotary_Encoder "has-a" Setlist
		self.displayed_msg = ""
		self.setlistName = set
		#load the set, song, and part that was last used that was saved to the default file
		self.setlist.loadSetlist(SET_FOLDER + set)
		self.currentSong = self.setlist.songs.head
		while self.currentSong.next is not None and song <> self.currentSong.data.name:
			self.currentSong = self.currentSong.next
		self.currentPart = self.currentSong.data.parts.head
		while self.currentPart.next is not None and part <> self.currentPart.data.partName:
			self.currentPart = self.currentPart.next
		self.changeToMenu("MainMenu") #starting menu
		#variables for the rotary movement interpretation loop
		self.lastGoodSeq = 0
		self.lastSeq = 0
		self.rotaryTimer = 0
		#keeps time for last rotary turn in seconds
		self.lastRotaryTurn = 0
		self.fontSize = 28
		self.fontType = 'upheavtt.ttf'

		
	def changePedalConfiguration(self, option):
		if option == "Song Down":
			if self.currentSong.prev is not None: 
				self.currentSong = self.currentSong.prev
				self.loadSong()
		elif option == "Part Down":
			if self.currentPart.prev is not None: 
				self.currentPart = self.currentPart.prev
				self.loadPart()
		elif option == "Part Up":
			if self.currentPart.next is not None: 
				self.currentPart = self.currentPart.next
				self.loadPart()
		elif option == "Song Up":
			if self.currentSong.next is not None: 
				self.currentSong = self.currentSong.next
				self.loadSong()
		elif option == "Main Menu":
			self.changeToMenu("MainMenu")
		elif option == "Switch Mode":
			for pedalObj in self.allPedals:
				if pedalObj.name == "RotaryPB":
					pedalObj.switchModes()
		

			
	def loadPart(self):
		tempoObj = None
		for pedalObj in self.allPedals:
			if pedalObj.name not in ["Empty", "RotaryPB", "TapTempo"]:
				state, setting = self.currentPart.data.PedalDictionary[pedalObj.name]
				if state:
					pedalObj.turnOn()
				else:
					pedalObj.turnOff()
				if setting is not None:
					pedalObj.setSetting(setting)
				if pedalObj.name == "TimeLine":
					pedalObj.setTempo(float(self.currentSong.data.bpm))
			elif pedalObj.name == "TapTempo":
				tempoObj = pedalObj #store this object for later use. 
				#need to get all the pedals to their correct state before messsing with tempo
		#now that we are out of the for loop, set the tempo
		self.setSongInfoMessage()
		if tempoObj is not None:
			tempoObj.setTempo(float(self.currentSong.data.bpm))
		self.savePartToDefault()
		EffectLoops.ButtonDisplay.currentButton_SongMode.invertDisplayColors = False
		#print EffectLoops.ButtonDisplay.currentButton_SongMode.name + " footswitch display to no longer be inverted" #testing
		
		EffectLoops.ButtonDisplay.currentButton_SongMode = self.pedalButtonDict[
					self.currentSong.data.parts.nodeToIndex(self.currentPart)]
		#print "footswitch display #" + str(self.currentSong.data.parts.nodeToIndex(
		#	self.currentPart)) + ": " + self.currentPart.data.partName + " set as new highlighted part." #testing

		#find the footswitch display associated with the part just loaded and invert its colors
		EffectLoops.ButtonDisplay.currentButton_SongMode.invertDisplayColors = True
		#print EffectLoops.ButtonDisplay.currentButton_SongMode.name + " footswitch display to now be inverted" #testing


	def rotaryMovement(self, a, b): 
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
		deltaTime = time.time() - self.rotaryTimer
		delta = abs(seq - self.lastSeq)
		if delta > 0:
			if seq == 1:
				if deltaTime < 0.05 and self.lastGoodSeq == 3:
					move = "CCW"
				else:
					move = "CW"
					self.lastGoodSeq = 1
					self.rotaryTimer = time.time()
			elif seq == 3:
				if deltaTime < 0.05 and self.lastGoodSeq == 1:
					move = "CW"
				else:    
					move = "CCW"
					self.lastGoodSeq = 3
					self.rotaryTimer = time.time()
			elif seq == 2:
				if self.lastGoodSeq == 1:
					move = "CW"
				elif self.lastGoodSeq == 3:
					move = "CCW"
		self.lastSeq = seq
		return move

		
	def getRotaryMovement(self, a, b):
		'''gets direction from rotary knob after making sure that the interrupts arent 
		happening too fast which might indicate false readings
		'''
		direction = self.rotaryMovement(a, b)
		if time.time() - self.lastRotaryTurn > 0.16: #0.08:
			self.lastRotaryTurn = time.time()
			return direction
		else:
			return None

			
	def menuFunction(self,func):
		'''do methods needed based on menu option chosen with rotary encoder and push button
		'''
		if func == "Set":
			#change menu list to a list of all sets in the sets folder set the menuposition to 0
			#and display the first item in the list
			self.currentMenu = "LoadSetMenu"
			setListFiles = os.listdir(SET_FOLDER)
			setlists = []
			for setListFile in setListFiles:
				if setListFile[-4:] == ".xml":
					newSetName = setListFile[:-4]
				setlists.append(newSetName)
			self.menuDictionary[self.currentMenu] = setlists
			self.changeToMenu("LoadSetMenu")
		elif func == "Song":
			#change menu list to a list of all songs in the current setlist, add the list to the menuDict
			#for the SongMenu item and change to the 'SongMenu' menu
			self.currentMenu = "SongMenu"
			self.menuDictionary[self.currentMenu] = self.setlist.songs
			self.currentSong = self.menuDictionary[self.currentMenu].head
			self.setMessage(self.currentSong.data.name)
		elif func == "Part":
			self.currentMenu = "PartMenu"
			self.menuDictionary[self.currentMenu] = self.currentSong.data.parts
			self.currentPart = self.menuDictionary[self.currentMenu].head
			self.setMessage(self.currentPart.data.partName)
		elif func == "Pedals":
			#display a list of pedals
			self.currentMenu = "PedalMenu"
			self.menuDictionary[self.currentMenu] = self.allPedals
			self.menuItems = self.menuDictionary[self.currentMenu]
			self.menuPos = 0
			self.setMessage(self.menuItems[self.menuPos].name + "\n" + str(self.menuItems[self.menuPos].getState()))
		elif func == "BPM":
			self.setMessage(self.currentSong.data.bpm)
		elif func == "Knob Color":
			self.changeToMenu("KnobMenu")
		elif func == "Knob Brightness":
			self.changeToMenu("BrightnessMenu")
		elif func == "Font Size":
			self.changeToMenu("FontSizeMenu")
		elif func == "Font Type":
			self.currentMenu = "LoadFontMenu"
			rawFontList = os.listdir(FONT_FOLDER)
			fontlist = []
			for rawfont in rawFontList:
				if rawfont[-4:] == ".ttf":
					newFontName = rawfont[:-4]
				fontlist.append(newFontName)
			self.menuDictionary[self.currentMenu] = fontlist
			self.changeToMenu("LoadFontMenu")
			#self.changeToMenu("fontTypeMenu")
		elif func in self.colorMenu:
			self.setColor(func)
			self.saveColorToDefault()
			self.changeToMenu("GlobalMenu")
		elif func in self.brightnessMenu:
			self.setBrightness(int(func))
			self.saveColorToDefault()
			self.changeToMenu("GlobalMenu")
		elif func == "Power down? \nno YES":
			self.setMessage("Goodbye.")
			self.lcd._delay_microseconds(1000000)
			self.lcd.set_backlight(0)
			os.system('shutdown now -h')
		elif func == "Power down? \nNO yes":
			self.changeToMenu("MainMenu")
		elif self.currentMenu == "LoadSetMenu":
			self.setMessage("Loading set...")
			self.setlistName = func
			self.setlist.loadSetlist(SET_FOLDER + func)
			self.currentSong = self.setlist.songs.head
			self.currentPart = self.currentSong.data.parts.head
			self.loadPart()
			self.updateButtonDisplays()
			self.changeToMenu("MainMenu")
		elif self.currentMenu == "LoadFontMenu":
			self.updateButtonDisplays(func, None)
			self.changeToMenu("GlobalMenu")
		elif self.currentMenu == "FontSizeMenu":
			self.updateButtonDisplays(None, func)
			self.changeToMenu("GlobalMenu")
		elif self.currentMenu == "PartMenu":
			self.loadPart()
			self.updateButtonDisplays()
			self.changeToMenu("MainMenu")
		elif self.currentMenu == "SongMenu":
			self.loadSong()
			self.changeToMenu("MainMenu")
		elif self.currentMenu == "PedalMenu":
			if self.menuItems[self.menuPos].isEngaged:
				self.menuItems[self.menuPos].turnOff()
			else:
				self.menuItems[self.menuPos].turnOn()
			self.setMessage(self.menuItems[self.menuPos].name + "\n" + str(self.menuItems[self.menuPos].getState()))

			
	def loadSong(self):
		self.currentPart = self.currentSong.data.parts.head
		for pedal in self.pedalButtonDict.values():
			pedal.invertDisplayColors = False
		self.loadPart()
		self.updateButtonDisplays()

		
	def changeMenuPos(self, direction):
		'''change the current position of the menu and display the new menu item
		unless the end or the beginning of the list has been reached
		'''
		if self.currentMenu == "PartMenu": #handle partmenu different; its a doublylinkedlist
			if direction == "CW":
				if self.currentPart.next is not None: 
					self.currentPart = self.currentPart.next
					self.setMessage(self.currentPart.data.partName)
			elif direction == "CCW":
				if self.currentPart.prev is not None:
					self.currentPart = self.currentPart.prev
					self.setMessage(self.currentPart.data.partName)
		elif self.currentMenu == "SongMenu":
			if direction == "CW":
				if self.currentSong.next is not None: 
					self.currentSong = self.currentSong.next
					self.displayWordWrap(self.currentSong.data.name)
			elif direction == "CCW":
				if self.currentSong.prev is not None:
					self.currentSong = self.currentSong.prev
					self.displayWordWrap(self.currentSong.data.name)
		elif self.currentMenu == "PedalMenu":
			if direction == "CW":
				if self.menuPos < len(self.menuItems) - 1:
					self.menuPos += 1
					self.setMessage(self.menuItems[self.menuPos].name + "\n" + str(self.menuItems[self.menuPos].getState()))
			elif direction == "CCW":
				if self.menuPos > 0:
					self.menuPos -= 1
					self.setMessage(self.menuItems[self.menuPos].name + "\n" + str(self.menuItems[self.menuPos].getState()))
		else:
			if direction == "CW":
				if self.menuPos < len(self.menuItems) - 1:
					self.menuPos += 1
					menuStr = self.menuItems[self.menuPos]
					if menuStr in ["SongInfo", "Set", "Song", "Part", "BPM"]:
						self.getMainMenuMessage(menuStr)
					else:
						self.setMessage(menuStr)
			elif direction == "CCW":
				if self.menuPos > 0:
					self.menuPos -= 1
					menuStr = self.menuItems[self.menuPos]
					if menuStr in ["SongInfo", "Set", "Song", "Part", "BPM"]:
						self.getMainMenuMessage(menuStr)
					else:
						self.setMessage(menuStr)

						
	def getMainMenuMessage(self, menuStr):
		if menuStr == "Set":
			self.setMessage(self.setlist.getSetlistName())
		elif menuStr == "SongInfo":
			self.setSongInfoMessage()
		elif menuStr == "Song":
			self.displayWordWrap(self.currentSong.data.name)
		elif menuStr == "Part":
			self.setMessage(self.currentPart.data.partName)
		else:
			self.setMessage(self.currentSong.data.bpm + "BPM")

			
	def getMenuItemString(self):
		'''get the current menu item from the menulist associated with the currentmenu
		'''
		if self.currentMenu == "PartMenu":
			return self.currentPart.data.partName
		if self.currentMenu == "SongMenu":
			return self.currentSong.data.name
		else:
			return self.menuDictionary[self.currentMenu][self.menuPos]

			
	def setMessage(self, msg):
		'''display a message on the lcd screen
		'''
		self.lcd.clear()
		self.lcd.message(msg)
		self.displayed_msg = msg

		
	def displayWordWrap(self, text):
		if len(text) > 16:
			overflow = len(text) - 16
			self.setMessage(text[:-overflow] + "\n" + text[-overflow:])
		else:
			self.setMessage(text)

			
	def setSongInfoMessage(self):
		self.setMessage(self.currentSong.data.name + "\n"
			+ self.currentSong.data.bpm + "BPM - " + self.currentPart.data.partName)

			
	def getMessage(self):
		'''return the message on the lcd screen
		'''
		return self.displayed_msg

		
	def changeToMenu(self, newMenu):
		'''change to a new menu based on the argument passed 'newMenu', redefine menuitems with the
		items associated with the new menu, set the menu  position to 0, and display the menu item 
		at the current postion.
		'''
		self.currentMenu = newMenu
		self.menuItems = self.menuDictionary[newMenu]
		self.menuPos = 0
		if newMenu == "MainMenu":
			self.getMainMenuMessage(self.menuItems[self.menuPos])
		else:
			self.setMessage(self.menuItems[self.menuPos])

		
	def getCurrentMenu(self):
		'''return the current menu 
		'''
		return self.currentMenu

		
	def setPedalsList(self, pedals, mode):
		'''sets the pedal list for the current pedal layout.
		pedals come in as a dictionary. "allPedals" is a list 
		of the objects from the pedals dictionary but stripped 
		of their respective button numbers.
		'''
		self.pedalButtonDict = {}
		self.pedalPinDict = pedals
		self.allPedals = self.pedalPinDict.values()
		for pedalObj in self.allPedals:
			if isinstance(pedalObj, EffectLoops.ButtonOnPedalBoard) and pedalObj.name != "RotaryPB":
				self.pedalButtonDict[pedalObj.button] = pedalObj
		if mode == "Song":
			self.changeToFootswitchItem()
			self.loadPart()
		self.switchModes(mode)

		
	def getPedalsList(self):
		'''returns the pedal list for the current pedal layout
		'''
		return self.allPedals

		
	def setTempMessage(self, tempMessage):
		savedMessage = self.getMessage()
		self.setMessage(tempMessage)
		self.lcd._delay_microseconds(1000000)
		self.setMessage(savedMessage)

		
	def saveColorToDefault(self):
		Defaults = ET.parse(DEFAULT_FILE)
		Root = Defaults.getroot()
		Root.find('knobColor').text = self.color 
		Root.find('knobBrightness').text = str(self.brightness) 
		Defaults.write(DEFAULT_FILE,encoding="us-ascii", xml_declaration=True)

		
	def savePartToDefault(self):
		Defaults = ET.parse(DEFAULT_FILE)
		Root = Defaults.getroot()
		Root.find('setList').text = self.setlistName
		Root.find('song').text = self.currentSong.data.name
		Root.find('part').text = self.currentPart.data.partName
		Defaults.write(DEFAULT_FILE,encoding="us-ascii", xml_declaration=True)
		
	
	def saveFontTypeToDefault(self, font_type):
		Defaults = ET.parse(DEFAULT_FILE)
		Root = Defaults.getroot()
		Root.find('fontType').text = font_type
		Defaults.write(DEFAULT_FILE,encoding="us-ascii", xml_declaration=True)
		
	def saveFontSizeToDefault(self, font_size):
		Defaults = ET.parse(DEFAULT_FILE)
		Root = Defaults.getroot()
		Root.find('fontSize').text = font_size
		Defaults.write(DEFAULT_FILE,encoding="us-ascii", xml_declaration=True)
	
	
	def updateButtonDisplays(self, ft=None, fs=None):
		if self.mode == "Song":
			songpart = self.currentSong.data.parts.head
			for i in range(1,10):
				if ft is not None:
					self.pedalButtonDict[i].setFont(fontType=ft)
				if fs is not None:
					self.pedalButtonDict[i].setFont(fontSize=fs)
				if songpart is not None:
					self.pedalButtonDict[i].setButtonDisplayMessage(songpart.data.partName, self.mode)
					songpart = songpart.next
				else:
					self.pedalButtonDict[i].setButtonDisplayMessage("", self.mode)
		else:
			for i in [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]:
				#if self.pedalButtonDict[i].name != "RotaryPB":
				if ft is not None:
					self.pedalButtonDict[i].setFont(fontType=ft)
				if fs is not None:
					self.pedalButtonDict[i].setFont(fontSize=fs)
				self.pedalButtonDict[i].setButtonDisplayMessage(self.pedalButtonDict[i].name, self.mode)
		if ft is not None:
			self.saveFontTypeToDefault(ft)
		if fs is not None:
			self.saveFontSizeToDefault(fs)

	
	def changeToFootswitchItem(self, button=None):
		if button is not None:
			if button <= self.currentSong.data.parts.getLength():
				self.currentPart = self.currentSong.data.parts.indexToNode(button)
				#print "\r\ncurrent part is now set to " + self.currentPart.data.partName #testing

				# EffectLoops.ButtonDisplay.currentButton_SongMode = self.pedalButtonDict[
				#	self.currentSong.data.parts.nodeToIndex(self.currentPart)]
				self.loadPart()
		#else:
			#self.pedalButtonDict[self.currentSong.data.parts.nodeToIndex(self.currentPart)].invertDisplayColors = True


class RotaryPushButton(EffectLoops.ButtonOnPedalBoard, Rotary_Encoder):
	'''class to handle button pushes on the rotary encoder knob. its parents are 'ButtonOnPedalBoard' from the 'EffectLoops' package
	and 'Rotary_Encoder' 
	'''
	def __init__(self, button, state, mode, **kwargs):
		type = "RotaryPushButton"
		FuncTwoType = "Settings"
		FuncTwoPort = "None"
		name = "RotaryPB"
		fontType = kwargs["ft"]
		fontSize = kwargs["fs"]
		Rotary_Encoder.__init__(self, **kwargs) #initialize parent class rotary encoder
		#initialize parent class buttonOnPedalboard
		super(RotaryPushButton, self).__init__(name, state, button, type, FuncTwoType, FuncTwoPort, ft=fontType, fs=fontSize)
		#self.switchModes(mode)
		
		
	def switchModes(self, mode=None):
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
		self.updateButtonDisplays(None, None)
		self.saveModeToDefault()
			
			
	def saveModeToDefault(self):
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
				menuItemStr = self.getMenuItemString()
				self.menuFunction(menuItemStr)
				if self.currentMenu == "GoodbyeMenu" and menuItemStr == "Power down? \nNO yes":
					self.changeToMenu("MainMenu")
			elif deltaT < 2: #longer than half a second but shorter than 2 seconds
				self.secondaryFunction()
			else: 
				if deltaT > 5: #if button held for more than 5 seconds
					self.changeToMenu("GoodbyeMenu")			
				elif self.currentMenu == "MainMenu": #otherwise if the button was pressed btwn 2 and 5 secs
					self.changeToMenu("GlobalMenu")	 #if the currentmenu is mainmenu swap to 'Global'
				else:
					self.changeToMenu("MainMenu")
			self.isPressed = False #was released
