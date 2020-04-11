#!/usr/bin/python
import time
from time import strftime
import math
import RPi.GPIO as GPIO #for interfacing with raspberrypi GPIO
import xml.etree.ElementTree as ET # for reading and writing to XML files

import EffectLoops #package for controlling the pedals
import Footswitches #package for the footswitch inputs
import RotaryEncoder #package for the rotary encoder inputs
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
formatter = logging.Formatter("%(asctime)s [midi_controller.py] [%(levelname)-5.5s]  %(message)s")
handler.setFormatter(formatter)
logger.addHandler(handler)

switch_pins = Footswitches.Looper_Switches() #class for dealing with footswitch presses
# previous_button_press = None
TapTempo = None

#read the default pedal arrangement file
default_pedals = ET.parse('/home/pi/Looper/Main/PedalGroup.xml') 
default_pedals_root = default_pedals.getroot() #assign the root of the file to a variable
Tempo = float(default_pedals_root.find('tempo').text) #get the default tempo
knob_color = default_pedals_root.find('knobColor').text #get the default encoder knob color
knob_brightness = int(default_pedals_root.find('knobBrightness').text) #get the default encoder knob brightness
mode = default_pedals_root.find('mode').text #get the mode of the looper (pedal or song)
setList = default_pedals_root.find('setList').text #get the default setlist
song = default_pedals_root.find('song').text #get the default song of the setlist
part = default_pedals_root.find('part').text #get the default part of the song
option_one = default_pedals_root.find('op1').text #options for changing pedal config
option_two = default_pedals_root.find('op2').text #when pressing two buttons simultaneously.
option_three = default_pedals_root.find('op3').text #the choices are song up, song down,
option_four = default_pedals_root.find('op4').text # part up, part down, other options
option_five = default_pedals_root.find('op5').text # including main menu
#set up rpi pins
#rotary encoder pins A & B go these pins on rpi
ENCODE_B = 23 
ENCODE_A = 24

#MCP23017 output interrupt pins for bank A (0 - 7) and B (8 - 15) go to these pins on rpi
BANKA_INTPIN = 4
BANKB_INTPIN = 17
#these are input pins on the MCP23017 for the tap button and the rotary encoders push button
ROTARY_PUSHBUTTON_PINNUMBER = 15
#TAP_TEMPO_BUTTONNUMBER = 10
#create a dictionary for pedals read from the pedals XML 
#with the 'key' being the pin that goes high when footswitch is pressed
#and 'value' is the pedal object associated with the switch press
pedal_dict = {"MIDITempoPedal":None}

#iterate the Default Pedals XML file
for current in default_pedals_root.iter('pedal'):
	try: #if the default pedal file is empty or one of the entries somehow doesnt have 'type'
		type = current.attrib["type"] #get the pedal type
	except:
		break #break out of the for loop on a read error
	if type == "MidiNonLoopPedal": #initialize a MidiNonLoopPedal object
		current_pedal = EffectLoops.MidiNonLoopPedal(current.attrib["name"], 
			bool(current.find("./engaged").text), int(current.find("./midiChannel").text),
			current.attrib["brand"], int(current.find("./preset").text))
		pedal_dict[current.attrib["name"]] = current_pedal
	elif type == "TimeLine": #initialize a TimeLine object
		current_pedal = EffectLoops.TimeLine(current.attrib["name"], 
			bool(current.find("./engaged").text), int(current.find("./midiChannel").text),
			current.attrib["brand"], Tempo, int(current.find("./preset").text))
		pedal_dict["MIDITempoPedal"] = current_pedal #assign this pedal to the dictionary
		
rotary_push_button = RotaryEncoder.RotaryPushButton(ROTARY_PUSHBUTTON_PINNUMBER, True, mode, 
	kc=knob_color, kb=knob_brightness, sl=setList, s=song, p=part) #initialize the rotaryencoder object
pedal_dict[str(rotary_push_button.getPin())] = rotary_push_button #assign this pedal to the dictionary

#passes a list of pedal objects to the rotary encoder
rotary_push_button.set_pedals_list(pedal_dict, mode)

#define the input pin on the rpi for the MCP23017 bank A and B footswitch interrupt
GPIO.setup([BANKA_INTPIN, BANKB_INTPIN], GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
#define the input pin on the rpi for the MCP23017 encode A and B input pins
GPIO.setup([ENCODE_B, ENCODE_A], GPIO.IN, pull_up_down=GPIO.PUD_UP)

#assign each footswitch (aside from rotary push button) a partner footswitch for double 
#footswitch press 'special functions'
for pin in pedal_dict:
	pedal = pedal_dict[pin]
	if isinstance(pedal, EffectLoops.ButtonOnPedalBoard) and pedal.name != "RotaryPB":
		pedal.set_partner(pedal_dict[str(pedal.from_button_to_pin(pedal.get_partner_button()))])
		
#funtion called when rotary knob is turned
def my_encoder_callback(EncoderInterruptPin):
	direction = rotary_push_button.get_rotary_movement(GPIO.input(ENCODE_A), GPIO.input(ENCODE_B))
	if direction is not None:
		rotary_push_button.change_menu_pos(direction)

#function called when any footswitch is pressed
def my_button_callback(interrupt_pin):
	logger.info("interrupt enter")
	#Which bank sent the interrupt; bank A (pin 4) mod 2 is 0; bank B (pin 17) mod 2 is 1
	interrupt_bank = interrupt_pin % 2  
	#read the interrupt register; find which pin and bank that caused the interrupt
	pin_caused_int = switch_pins.IntrptFlagRegister(interrupt_bank)
	#if the pin is equal to zero, interrupt should not happen
	if pin_caused_int != 0:
		#doing a read on the interrupt register returns an 8 bit binary number
		#where pin n returns 2^n. log returns a floating point so turn that into a integer
		#and add 8 for bank B. interrupt bank is either 0 or 1 from above.
		intFlagPin = int(math.log(pin_caused_int,2)) + 8*interrupt_bank
		logger.info("bank: " + str(interrupt_bank) + "; pin: " + str(intFlagPin) + "; interrupt  Register = " + str(pin_caused_int))
		#look up the pedal object that caused the interrupt and assign it to interrupt pedal
		int_pedal = pedal_dict[str(intFlagPin)]
		time.sleep(.005)
		#disable the interrupts for that particular pin until the read of the value of that pin at the time of 
		#the interrupt is complete other wise the interrupt would be reset on read.
		switch_pins.disableInterruptPin(intFlagPin)
		#read value of the pin that caused the interrupt at the time of the interrupt
		interrupt_value = switch_pins.readIntrptCapPin(intFlagPin)
		logger.info("interrupt pin's value: " + str(interrupt_value))
		#rotary push button does not have a "partner" so no need to check that one
		if int_pedal.name != "RotaryPB":
			#print interrupt_bank, intFlagPin #TESTING PURPOSES
			#check to see if the footswitch was pressed in combination with its partner for the 2-button function
			#like bank up, bank down, next song, etc.
			if int_pedal.partner.is_pressed:
				if interrupt_value: 
					option_type = None
					#do the 2-button function for the pedal that called it
					f = int_pedal.partner.get_partner_function()
					if f == 1:
						option_type = option_one
					elif f == 2:
						option_type = option_two
					elif f == 3:
						option_type = option_three
					elif f == 4:
						option_type = option_four
					elif f == 5:
						option_type = option_five
					rotary_push_button.change_pedal_configuration(option_type)
					int_pedal.PedalConfigChanged = True
					#int_pedal.partner.PedalConfigChanged == True  
					logger.info( "double footswitch function: " + option_type)
			else:
				#button state determines which function of the pedal whose footswitch was pressed to use
				int_pedal.button_state(interrupt_value, rotary_push_button.mode)
				if interrupt_value:
					if rotary_push_button.mode == "Song" and time.time() - int_pedal.last_action_time <= 0.5:
						rotary_push_button.change_to_footswitch_item(int_pedal.button)
			int_pedal.last_action_time = time.time()
		else:
			#button state determines which function of the pedal whose footswitch was pressed to use
			int_pedal.button_state(interrupt_value)
		#reenable the interrupts on the pin of the footswitch that was pressed		
		switch_pins.enableInterruptPin(intFlagPin)
	#else:
		#print "bank: " + str(interrupt_bank) + "; pin: " + str(pin_caused_int) + "; DIDNT GO IN 'IF' STATEMENT"
	#print "interrupt exit"

		
#define the interrupt for the MCP23017 bank A and B for the footswitches
GPIO.add_event_detect(BANKA_INTPIN, GPIO.RISING, callback=my_button_callback, bouncetime=5)
GPIO.add_event_detect(BANKB_INTPIN, GPIO.RISING, callback=my_button_callback, bouncetime=5)
#define the interrupt for the MCP23017 encode pin A and B for the rotary encoder
GPIO.add_event_detect(ENCODE_A, GPIO.BOTH, callback=my_encoder_callback)
GPIO.add_event_detect(ENCODE_B, GPIO.BOTH, callback=my_encoder_callback)


try:
	while 1:
		#pass
		time.sleep(0.1)
		if TapTempo is not None:
			if TapTempo.tapping_in_progress and (time.time() - TapTempo.tap_start_time) > TapTempo.pwm_on_time:
				TapTempo.pause_pwm()
		#pedal_dict['12'].setButtonDisplayMessage(strftime("%I:%M"),"")
except KeyboardInterrupt:
	pass

rotary_push_button.stop_pwm #this will cause the PWM to stop if anything causes the program to stop
if TapTempo is not None:
	TapTempo.stop_pwm()
EffectLoops.unload()
