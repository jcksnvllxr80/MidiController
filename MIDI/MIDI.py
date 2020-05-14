#import serial #if using pi for MIDI. I changed to using the Arduino Pro Micro 
#import smbus #used for i2c #THE OLD i2c WAY
import Adafruit_GPIO.I2C as I2C # THE NEW WAY
import time
import logging

'''   ############ USAGE ###############
logger.debug("debug message")
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
formatter = logging.Formatter("%(asctime)s [MIDI.py] [%(levelname)-5.5s]  %(message)s")
handler.setFormatter(formatter)
logger.addHandler(handler)

i2c_device = I2C.get_i2c_device(address=0x04, busnum=I2C.get_default_bus())


class MIDI(object):
        
	CCdict = {"1":"\xB0", "2":"\xB1", "3":"\xB2", "4":"\xB3", "5":"\xB4", 
		"6":"\xB5", "7":"\xB6", "8":"\xB7", "9":"\xB8", "10":"\xB9", "11":"\xBA", 
		"12":"\xBB", "13":"\xBC", "14":"\xBD", "15":"\xBE", "16":"\xBF"}
	PCdict = {"1":"\xC0", "2":"\xC1", "3":"\xC2", "4":"\xC3", "5":"\xC4", 
		"6":"\xC5", "7":"\xC6", "8":"\xC7", "9":"\xC8", "10":"\xC9", "11":"\xCA", 
		"12":"\xCB", "13":"\xCC", "14":"\xCD", "15":"\xCE", "16":"\xCF"}

	def __init__(self, channel):
		self.CCchannel = self.CCdict[str(channel)]
		self.PCchannel = self.PCdict[str(channel)]

	def MIDI_CC_TX(self, changeNum, value):
		message = self.CCchannel + changeNum + value
		self.write(message)

	def MIDI_PC_TX(self, changeNum, value):
		message = self.PCchannel + changeNum + value
		self.write(message)

	def SysEx_TX(self, message):
		self.write(message)

	#def SoftThru(self):	#FUTURE USE
	#	self._devices.read_byte(self.address)
		#self.write(ser.read(1))

	# def StrymonPresetChange(self, presetGroup, preset):
	# 	message = self.CCchannel + presetGroup + self.PCchannel + preset
	# 	self.write(message)

	# def SelahPresetChange(self, preset, value):
	# 	message = self.CCchannel + preset + value
	# 	self.write(message)
		
	# def	SelahPresetTempoChange(self, preset):
	# 	message = self.PCchannel + preset
	# 	self.write(message)
		
	def write(self, msg):
		logger.info("MIDI sent: " + repr(msg))
		for byte in msg:
			i2c_device.writeRaw8(ord(byte))
			time.sleep(0.0001)
