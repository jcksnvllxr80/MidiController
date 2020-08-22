import time
import logging
import Adafruit_GPIO.SPI as SPI
import SSD1306
import RPi.GPIO as GPIO
from PIL import Image
from PIL import ImageFont
from PIL import ImageDraw


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

	def __init__(self, ft=None, fs=None):	
		self.spi_disp = SSD1306.SSD1306_128_64(
			rst=RST, dc=DC, spi=SPI.SpiDev(SPI_PORT, SPI_DEVICE, max_speed_hz=8000000)
		)
		if ft is None and fs is None:
			self.set_font()
			self.invert_display_colors = False
			self.spi_disp.begin()
			self.width = self.spi_disp.width
			self.height = self.spi_disp.height
			self.clear_display()
			self.display_image = None
		else:
			self.set_font(ft, fs)


	def _delay_microseconds(self, microseconds):
		end = time.time() + (microseconds/1000000.0)
		while time.time() < end:
			pass


	def set_display_message(self, msg):
		self.message = msg
		backgroundColor = 0
		textColor = 255
		image = Image.new('1', (self.width, self.height))
		draw = ImageDraw.Draw(image)
		# Clear image buffer by drawing a black filled box.
		if self.invert_display_colors:
			backgroundColor = 255
			textColor = 0
			
		draw.rectangle((0,0,self.width,self.height), outline=backgroundColor, fill=backgroundColor)
		y = 0
		if self.display_image is not None:
			image = Image.open(IMG_FOLDER + self.display_image + '.ppm').convert('1') #for testing. comment when not testing
		else:
			self.draw_left_justified(msg, draw, y, textColor)
			# self.draw_centered(msg, draw, y, textColor)
		self.spi_disp.image(image)
		self.spi_disp.display()


	def draw_centered(self, msg, draw, y, textColor):
		for str in msg.split(" - "):
			xMax, yMax = draw.textsize(str, font=self.font_type)
			x = (self.width - xMax)/2
			draw.text((x, y), str, font=self.font_type, fill=textColor) 
			y += yMax + 2


	def draw_left_justified(self, msg, draw, y, textColor):
		for str in msg.split(" - "):
			xMax, yMax = draw.textsize(str, font=self.font_type)
			x = 0
			draw.text((x, y), str, font=self.font_type, fill=textColor) 
			y += yMax + 2


	def set_font(self, font_type=None, font_size=None):
		if font_size:
			self.font_size = int(font_size)
		else:
			self.font_size = 9

		if font_type:
			self.font_type = ImageFont.truetype(FONT_FOLDER + font_type + ".ttf", self.font_size)
		else:
			self.font_type = ImageFont.load_default()


	def set_display_image(self, filename):
		self.display_image = filename
		logger.info("Image set.")


	def clear_display(self):
		self.spi_disp.clear()
		self.spi_disp.display()
		logger.info("Cleared OLED screen.")
