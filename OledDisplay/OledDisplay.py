import time
import logging
import Adafruit_GPIO.SPI as SPI
import SSD1306
import RPi.GPIO as GPIO
from PIL import Image
from PIL import ImageFont
from PIL import ImageDraw
import subprocess


RST = 25
DC = 12
SPI_PORT = 0
SPI_DEVICE = 0
FONT_FOLDER = '/home/pi/MidiController/SSD1306/font/'
IMG_FOLDER = '/home/pi/MidiController/SSD1306/images/'

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
formatter = logging.Formatter("%(asctime)s [OledDisplay.py] [%(levelname)-5.5s]  %(message)s")
handler.setFormatter(formatter)
logger.addHandler(handler)

class OledDisplay(object):
	font_type = None
	font_size = None
	show_stats = False

	def __init__(self, ft=None, fs=None):	
		self.spi_disp = SSD1306.SSD1306_128_64(
			rst=RST, dc=DC, spi=SPI.SpiDev(SPI_PORT, SPI_DEVICE, max_speed_hz=8000000)
		)
		if ft is None and fs is None:
			self.set_font()
			self.invertDisplayColors = False
			self.spi_disp.begin()
			self.width = self.spi_disp.width
			self.height = self.spi_disp.height
			self.clear_display()
			self.displayImage = None
		else:
			self.set_font(ft, fs)
	

	def _delay_microseconds(self, microseconds):
		end = time.time() + (microseconds/1000000.0)
		while time.time() < end:
			pass


	def setDisplayMessage(self, msg):
		self.message = msg
		backgroundColor = 0
		textColor = 255
		image = Image.new('1', (self.width, self.height))
		draw = ImageDraw.Draw(image)
		# Clear image buffer by drawing a black filled box.
		if self.invertDisplayColors:
			backgroundColor = 255
			textColor = 0
			
		draw.rectangle((0,0,self.width,self.height), outline=backgroundColor, fill=backgroundColor)
		y = 0
		if self.displayImage is not None:
			image = Image.open(IMG_FOLDER + self.displayImage + '.ppm').convert('1') #for testing. comment when not testing
		else:
			for str in msg.split(" - "):
				xMax, yMax = draw.textsize(str, font=self.font_type)
				x = (self.width - xMax)/2
				draw.text((x, y), str, font=self.font_type, fill=textColor) 
				y += yMax + 2
		self.spi_disp.image(image)
		self.spi_disp.display()


	def set_font(self, font_type=None, font_size=None):
		if font_size:
			self.font_size = int(font_size)
		else:
			self.font_size = 9

		if font_type:
			self.font_type = ImageFont.truetype(FONT_FOLDER + font_type + ".ttf", self.font_size)
		else:
			self.font_type = ImageFont.load_default()


	def setDisplayImage(self, filename):
		self.displayImage = filename
		logger.info("Image set.")


	def clear_display(self):
		self.spi_disp.clear()
		self.spi_disp.display()
		logger.info("Cleared OLED screen.")


	def display_stats(self):
		self.show_stats	= True
		image = Image.new('1', (self.width, self.height))
		draw = ImageDraw.Draw(image)
		# Draw a black filled box to clear the image.
		draw.rectangle((0,0,self.width,self.height), outline=0, fill=0)
		# Draw some shapes.
		# First define some constants to allow easy resizing of shapes.
		padding = -2
		top = padding
		# Move left to right keeping track of the current x position for drawing shapes.
		x = 0
		while True:
			# Draw a black filled box to clear the image.
			draw.rectangle((0,0,self.width,self.height), outline=0, fill=0)
			# Shell scripts for system monitoring from here : https://unix.stackexchange.com/questions/119126/command-to-display-memory-usage-disk-usage-and-cpu-load
			cmd = "hostname -I | cut -d\' \' -f1"
			IP = subprocess.check_output(cmd, shell = True )
			cmd = "top -bn1 | grep load | awk '{printf \"CPU Load: %.2f\", $(NF-2)}'"
			CPU = subprocess.check_output(cmd, shell = True )
			cmd = "free -m | awk 'NR==2{printf \"Mem: %s/%sMB %.2f%%\", $3,$2,$3*100/$2 }'"
			MemUsage = subprocess.check_output(cmd, shell = True )
			cmd = "df -h | awk '$NF==\"/\"{printf \"Disk: %d/%dGB %s\", $3,$2,$5}'"
			Disk = subprocess.check_output(cmd, shell = True )

			# Write two lines of text.
			draw.text((x, top),       "IP: " + str(IP),  font=self.font_type, fill=255)
			draw.text((x, top+8),     str(CPU), font=self.font_type, fill=255)
			draw.text((x, top+16),    str(MemUsage),  font=self.font_type, fill=255)
			draw.text((x, top+25),    str(Disk),  font=self.font_type, fill=255)

			self.spi_disp.image(image)
			if self.show_stats:
				# Display image.
				self.spi_disp.display()
				time.sleep(.1)
			else:
				break
