import time
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
FONT_FOLDER = '/home/pi/Looper/SSD1306/font/'
IMG_FOLDER = '/home/pi/Looper/SSD1306/images/'

class ButtonDisplay(object):
  font_type = None
  font_size = 0
  spi_disp = SSD1306.SSD1306_128_64(rst=RST, dc=DC, spi=SPI.SpiDev(SPI_PORT, SPI_DEVICE, max_speed_hz=8000000))

  def __init__(self, ft=None, fs=None):	
		if ft is None and fs is None:
			self.invertDisplayColors = False
			self.spiEnable()
			self.spi_disp.begin()
			self.width = self.spi_disp.width
			self.height = self.spi_disp.height
			self.spi_disp.clear()
			self.spi_disp.display()
			self.spiDisable()
			self.pedalImage = None
		else:
			ButtonDisplay.font_type = ft
			ButtonDisplay.font_size = fs


  def setButtonDisplayMessage(self, msg, mode):
		self.message = msg
		backgroundColor = 0
		textColor = 255
		image = Image.new('1', (self.width, self.height))
		font = ImageFont.truetype(FONT_FOLDER + self.font_type + ".ttf", self.font_size)
		draw = ImageDraw.Draw(image)
		# Clear image buffer by drawing a black filled box.
		if self.invertDisplayColors and mode == "Song":
			backgroundColor = 255
			textColor = 0
			
		draw.rectangle((0,0,self.width,self.height), outline=backgroundColor, fill=backgroundColor)
		y = 0
		if self.pedalImage is not None:
			image = Image.open(IMG_FOLDER + self.pedalImage + '.ppm').convert('1') #for testing. comment when not testing
		else:
			for str in msg.split(" "):
				xMax, yMax = draw.textsize(str, font=font)
				x = (self.width - xMax)/2
				draw.text((x, y), str, font=font, fill=textColor) 
				y += yMax + 2

		self.spiEnable()
		self.spi_disp.image(image)
		self.spi_disp.display()
		self.spiDisable()


  def setFont(self, fontType=None, fontSize=None):
    if fontType is not None:
      ButtonDisplay.font_type = fontType
    if fontSize is not None:
      ButtonDisplay.font_size = int(fontSize)	

  
  def spiEnable(self):
		pass
    # not implemented


  def spiDisable(self):
		pass
    # not implemented


  def setPedalImage(self, filename):
		self.pedalImage = filename
