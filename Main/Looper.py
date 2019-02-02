#!/usr/bin/python
import time
from time import strftime
import math
import RPi.GPIO as GPIO #for interfacing with raspberrypi GPIO
import xml.etree.ElementTree as ET # for reading and writing to XML files

import EffectLoops #package for controlling the pedals
import Footswitches #package for the footswitch inputs
import RotaryEncoder #package for the rotary encoder inputs

switchPins = Footswitches.Looper_Switches() #class for dealing with footswitch presses
previousButtonPress = None
TapTempo = None

#read the default pedal arrangement file
DefaultPedals = ET.parse('/home/pi/Looper/Main/PedalGroup.xml') 
DefaultPedalsRoot = DefaultPedals.getroot() #assign the root of the file to a variable
Tempo = float(DefaultPedalsRoot.find('tempo').text) #get the default tempo
knobColor = DefaultPedalsRoot.find('knobColor').text #get the default encoder knob color
knobBrightness = int(DefaultPedalsRoot.find('knobBrightness').text) #get the default encoder knob brightness
mode = DefaultPedalsRoot.find('mode').text #get the mode of the looper (pedal or song)
fontType = DefaultPedalsRoot.find('fontType').text #get the fontType
fontSize = int(DefaultPedalsRoot.find('fontSize').text) #get the fontSize
setList = DefaultPedalsRoot.find('setList').text #get the default setlist
song = DefaultPedalsRoot.find('song').text #get the default song of the setlist
part = DefaultPedalsRoot.find('part').text #get the default part of the song
option_one = DefaultPedalsRoot.find('op1').text #options for changing pedal config
option_two = DefaultPedalsRoot.find('op2').text #when pressing two buttons simultaneously.
option_three = DefaultPedalsRoot.find('op3').text #the choices are song up, sopng down,
option_four = DefaultPedalsRoot.find('op4').text # part up, part down, other options
option_five = DefaultPedalsRoot.find('op5').text # including main menu
#set up rpi pins
#rotary encoder pins A & B go these pins on rpi
ENCODE_B = 23 
ENCODE_A = 24
OLED_RESET = 25

#MCP23017 output interrupt pins for bank A (0 - 7) and B (8 - 15) go to these pins on rpi
BANKA_INTPIN = 4
BANKB_INTPIN = 17
#these are input pins on the MCP23017 for the tap button and the rotary encoders push button
ROTARY_PUSHBUTTON_PINNUMBER = 15
#TAP_TEMPO_BUTTONNUMBER = 10
#create a dictionary for pedals read from the pedals XML 
#with the 'key' being the pin that goes high when footswitch is pressed
#and 'value' is the pedal object associated with the switch press
PedalDict = {"MIDITempoPedal":None}

# Reset OLEDs to begin initialization
GPIO.setup(OLED_RESET, GPIO.OUT) #make output
GPIO.output(OLED_RESET, GPIO.HIGH)
time.sleep(0.001)
GPIO.output(OLED_RESET, GPIO.LOW)
time.sleep(0.010)
GPIO.output(OLED_RESET, GPIO.HIGH)

#iterate the Default Pedals XML file
for current in DefaultPedalsRoot.iter('pedal'):
	try: #if the default pedal file is empty or one of the entries somehow doesnt have 'type'
		type = current.attrib["type"] #get the pedal type
	except:
		break #break out of the for loop on a read error
	if type == "LoopPedal": #initialize a LoopPedal object
		currentPedal = EffectLoops.LoopPedal(current.attrib["name"], 
			int(current.find("./button").text), bool(current.find("./engaged").text),
			current.find("./funcTwoType").text, current.find("./funcTwoPort").text)
		PedalDict[str(currentPedal.getPin())] = currentPedal #assign this pedal to the dictionary
	elif type == "MidiLoopPedal":  #initialize a MidiLoopPedal object
		currentPedal = EffectLoops.MidiLoopPedal(current.attrib["name"], 
			int(current.find("./button").text), bool(current.find("./engaged").text),
			str(current.find("./preset").text), int(current.find("./midiChannel").text), 
			current.find("./funcTwoType").text, current.find("./funcTwoPort").text, 
			current.attrib["brand"])
		PedalDict[str(currentPedal.getPin())] = currentPedal #assign this pedal to the dictionary
	elif type == "MidiNonLoopPedal": #initialize a MidiNonLoopPedal object
		currentPedal = EffectLoops.MidiNonLoopPedal(current.attrib["name"], 
			bool(current.find("./engaged").text), int(current.find("./midiChannel").text),
			current.attrib["brand"], int(current.find("./preset").text))
		PedalDict[current.attrib["name"]] = currentPedal
	elif type == "TimeLine": #initialize a TimeLine object
		currentPedal = EffectLoops.TimeLine(current.attrib["name"], 
			bool(current.find("./engaged").text), int(current.find("./midiChannel").text),
			current.attrib["brand"], Tempo, int(current.find("./preset").text))
		PedalDict["MIDITempoPedal"] = currentPedal #assign this pedal to the dictionary
	elif type == "Empty": #initialize an Empty object for loops not associated with pedals
		currentPedal = EffectLoops.Empty(current.attrib["name"], int(current.find("./button").text), True)
		PedalDict[str(currentPedal.getPin())] = currentPedal #assign this pedal to the dictionary
	elif type == "TapTempo": #initialize the TapTempoButton object
		currentPedal = EffectLoops.TapTempoButton("TapTempo", int(current.find("./button").text),
			Tempo, PedalDict["MIDITempoPedal"]) 
		PedalDict[str(currentPedal.getPin())] = currentPedal #assign this pedal to the dictionary
		TapTempo = currentPedal
		
RotaryPB = RotaryEncoder.RotaryPushButton(ROTARY_PUSHBUTTON_PINNUMBER, True, mode, ft=fontType, 
	fs=fontSize, kc=knobColor, kb=knobBrightness, sl=setList, s=song, p=part) #initialize the rotaryencoder object
PedalDict[str(RotaryPB.getPin())] = RotaryPB #assign this pedal to the dictionary
#set the current footswitch display associated with tht eloaded part to inverted colors
EffectLoops.ButtonDisplay.currentButton_SongMode = PedalDict[str(RotaryPB.fromButtonToPin(
	RotaryPB.currentSong.data.parts.nodeToIndex(RotaryPB.currentPart)))]

#print "footswitch display #" + str(RotaryPB.currentSong.data.parts.nodeToIndex(RotaryPB.currentPart)) + " set as initial highlighted part." #testing

#passes a list of pedal objects to the rotary encoder
RotaryPB.setPedalsList(PedalDict, mode)
#RotaryPB.switchModes(mode)

#define the input pin on the rpi for the MCP23017 bank A and B footswitch interrupt
GPIO.setup([BANKA_INTPIN, BANKB_INTPIN], GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
#define the input pin on the rpi for the MCP23017 encode A and B input pins
GPIO.setup([ENCODE_B, ENCODE_A], GPIO.IN, pull_up_down=GPIO.PUD_UP)

#assign each footswitch (aside from rotary push button) a partner footswitch for double 
#footswitch press 'special functions'
for pin in PedalDict:
    pedal = PedalDict[pin]
    if isinstance(pedal, EffectLoops.ButtonOnPedalBoard) and pedal.name != "RotaryPB":    
		pedal.setPartner(PedalDict[str(pedal.fromButtonToPin(pedal.getPartnerButton()))])
		
#funtion called when rotary knob is turned
def myEncoderCallback(EncoderInterruptPin):
	direction = RotaryPB.getRotaryMovement(GPIO.input(ENCODE_A), GPIO.input(ENCODE_B))
	if direction is not None:
		RotaryPB.changeMenuPos(direction)

#function called when any footswitch is pressed
def myButtonCallback(interruptPin):
	#print "interrupt enter"
	#Which bank sent the interrupt; bank A (pin 4) mod 2 is 0; bank B (pin 17) mod 2 is 1
	interruptBank = interruptPin % 2  
	#read the interrupt register; find which pin and bank that caused the interrupt
	ThePinThatCausedTheInt = switchPins.IntrptFlagRegister(interruptBank)
	#if the pin is equal to zero, interrupt should not happen
	if ThePinThatCausedTheInt != 0:
		#doing a read on the interrupt register returns an 8 bit binary number
		#where pin n returns 2^n. log returns a floating point so turn that into a integer
		#and add 8 for bank B. interrupt bank is either 0 or 1 from above.
		intFlagPin = int(math.log(ThePinThatCausedTheInt,2)) + 8*interruptBank
		#print "bank: " + str(interruptBank) + "; pin: " + str(intFlagPin) + "; interrupt  Register = " + str(ThePinThatCausedTheInt)
		#look up the pedal object that caused the interrupt and assign it to interrupt pedal
		intPedal = PedalDict[str(intFlagPin)]
		time.sleep(.005)
		#disable the interrupts for that particular pin until the read of the value of that pin at the time of 
		#the interrupt is complete other wise the interrupt would be reset on read.
		switchPins.disableInterruptPin(intFlagPin)
		#read value of the pin that caused the interrupt at the time of the interrupt
		interruptValue = switchPins.readIntrptCapPin(intFlagPin)
		#rotary push button does not have a "partner" so no need to check that one
		if intPedal.name != "RotaryPB":
			#print interruptBank, intFlagPin #TESTING PURPOSES
			#check to see if the footswitch was pressed in combination with its partner for the 2-button function
			#like bank up, bank down, next song, etc.
			if intPedal.partner.isPressed:
				if interruptValue: 
					#do the 2-button function for the pedal that called it
					f = intPedal.partner.getPartnerFunction()
					if f == 1:
						RotaryPB.changePedalConfiguration(option_one)
					elif f == 2:
						RotaryPB.changePedalConfiguration(option_two)
					elif f == 3:
						RotaryPB.changePedalConfiguration(option_three)
					elif f == 4:
						RotaryPB.changePedalConfiguration(option_four)
					elif f == 5:
						RotaryPB.changePedalConfiguration(option_five)
					intPedal.PedalConfigChanged == True
					#intPedal.partner.PedalConfigChanged == True  
					#print "double footswitch function"
			else:
				#button state determines which function of the pedal whose footswitch was pressed to use
				intPedal.buttonState(interruptValue, RotaryPB.mode)
				if interruptValue:
					if RotaryPB.mode == "Song" and time.time() - intPedal.lastActionTime <= 0.5:
						RotaryPB.changeToFootswitchItem(intPedal.button)
					RotaryPB.updateButtonDisplays(None, None)
			intPedal.lastActionTime = time.time()
		else:
			#button state determines which function of the pedal whose footswitch was pressed to use
			intPedal.buttonState(interruptValue)
		#reenable the interrupts on the pin of the footswitch that was pressed		
		switchPins.enableInterruptPin(intFlagPin)
	#else:
		#print "bank: " + str(interruptBank) + "; pin: " + str(ThePinThatCausedTheInt) + "; DIDNT GO IN 'IF' STATEMENT"
	#print "interrupt exit"

		
#define the interrupt for the MCP23017 bank A and B for the footswitches
GPIO.add_event_detect(BANKA_INTPIN, GPIO.RISING, callback=myButtonCallback, bouncetime=5)
GPIO.add_event_detect(BANKB_INTPIN, GPIO.RISING, callback=myButtonCallback, bouncetime=5)
#define the interrupt for the MCP23017 encode pin A and B for the rotary encoder
GPIO.add_event_detect(ENCODE_A, GPIO.FALLING, callback=myEncoderCallback, bouncetime=1)
GPIO.add_event_detect(ENCODE_B, GPIO.FALLING, callback=myEncoderCallback, bouncetime=1)


try:
	while 1:
		#pass
		time.sleep(0.1)
		if TapTempo is not None:
			if TapTempo.tappingInProgress and (time.time() - TapTempo.tapStartTime) > TapTempo.PWM_OnTime:
				TapTempo.pausePWM()
		#PedalDict['12'].setButtonDisplayMessage(strftime("%I:%M"),"")
except KeyboardInterrupt:
	pass

RotaryPB.stopPWM #this will cause the PWM to stop if anything causes the program to stop
if TapTempo is not None:
	TapTempo.stopPWM()