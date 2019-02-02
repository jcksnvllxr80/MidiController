import math
import Adafruit_GPIO as GPIO
import Adafruit_GPIO.I2C as I2C

class MCP230xxBase(GPIO.BaseGPIO):
	"""Base class to represent an MCP230xx series GPIO extender.  Is compatible
	with the Adafruit_GPIO BaseGPIO class so it can be used as a custom GPIO
	class for interacting with device.
	"""

	def __init__(self, address, i2c=None, **kwargs):
		"""Initialize MCP230xx at specified I2C address and bus number.  If bus
		is not specified it will default to the appropriate platform detected bus.
		"""
		# Create I2C device.
		if i2c is None:
			import Adafruit_GPIO.I2C as I2C
			i2c = I2C
		self._device = i2c.get_i2c_device(address, **kwargs)
		# Assume starting in ICON.BANK = 0 mode (sequential access).
		# Compute how many bytes are needed to store count of GPIO.
		self.gpio_bytes = int(math.ceil(self.NUM_GPIO/8.0))
		# Buffer register values so they can be changed without reading.
		self.iodir = [0x00]*self.gpio_bytes  # Default direction to all inputs.
		self.gppu = [0x00]*self.gpio_bytes  # Default to pullups disabled.
		self.gpio = [0x00]*self.gpio_bytes
		self.gpinten = [0x00]*self.gpio_bytes
		self.defval = [0x00]*self.gpio_bytes
		self.intcon = [0x00]*self.gpio_bytes
		self.iocon = [0x00]*self.gpio_bytes
		self.inputPolarity = [0x00]*self.gpio_bytes
		# Write current direction and pullup buffer state.
		self.write_iodir()
		self.write_gppu()

	def setup(self, pin, value):
		"""Set the input or output mode for a specified pin.  Mode should be
		either GPIO.OUT or GPIO.IN.
		"""
		self._validate_pin(pin)
		# Set bit to 1 for input or 0 for output.
		if value == GPIO.IN:
			self.iodir[int(pin/8)] |= 1 << (int(pin%8))
		elif value == GPIO.OUT:
			self.iodir[int(pin/8)] &= ~(1 << (int(pin%8)))
		else:
			raise ValueError('Unexpected value.  Must be GPIO.IN or GPIO.OUT.')
		self.write_iodir()

	def readGpioByte(self, bank):
		assert (bank == 0 or bank == 1),"bank must be 0 or 1"
		if bank:
			gpioByte = self._device.readU8(self.GPIOB)
		else:
			gpioByte = self._device.readU8(self.GPIOA)
		return gpioByte

	def inputPolarity_pin(self, pin, value):
		"""Set the input polarity for a specified pin.  Mode should be
		either SET or CLEAR.
		"""
		self._validate_pin(pin)
		# Set bit to 1 for input or 0 for output.
		if value == True:
			self.inputPolarity[int(pin/8)] |= 1 << (int(pin%8))
		elif value == False:
			self.inputPolarity[int(pin/8)] &= ~(1 << (int(pin%8)))
		else:
			raise ValueError('Unexpected value.  Must be GPIO.IN or GPIO.OUT.')
		self.write_inputPolarity()

	def gpinten_pin(self, pin, value):
		"""Set the input or output mode for a specified pin.  Mode should be
		either GPIO.OUT or GPIO.IN.
		"""
		self._validate_pin(pin)
		# Set bit to 1 for input or 0 for output.
		if value == GPIO.IN:
			self.gpinten[int(pin/8)] |= 1 << (int(pin%8))
		elif value == GPIO.OUT:
			self.gpinten[int(pin/8)] &= ~(1 << (int(pin%8)))
		else:
			raise ValueError('Unexpected value.  Must be GPIO.IN or GPIO.OUT.')
		self.write_gpinten()

	def gpintdisable_byte(self, dataByte, bank):
		assert (bank == 0 or bank == 1),"bank must be 0 or 1"
		if bank:
			existingIntEnableByte = self._device.readU8(self.GPINTENB)
			newDataByte = existingIntEnableByte ^ dataByte
			self._device.write8(self.GPINTENB, newDataByte)
		else:
			existingIntEnableByte = self._device.readU8(self.GPINTENA)
			newDataByte = existingIntEnableByte ^ dataByte
			self._device.write8(self.GPINTENA, newDataByte)

	def gpintenable_byte(self, dataByte, bank):
		assert (bank == 0 or bank == 1),"bank must be 0 or 1"
		if bank:
			existingIntEnableByte = self._device.readU8(self.GPINTENB)
			newDataByte = existingIntEnableByte | dataByte
			self._device.write8(self.GPINTENB, newDataByte)
		else:
			existingIntEnableByte = self._device.readU8(self.GPINTENA)
			newDataByte = existingIntEnableByte | dataByte
			self._device.write8(self.GPINTENA, newDataByte)

	def writeGpioByte(self, dataByte, bank):
		assert (bank == 0 or bank == 1),"bank must be 0 or 1"
		if bank:
			self._device.write8(self.GPIOB, dataByte)
		else:
			self._device.write8(self.GPIOA, dataByte)

	def iocon_pin2(self):
		"""Set the input or output mode for a specified pin.  Mode should be
		either GPIO.OUT or GPIO.IN.
		"""
		self._device.write8(self.IOCON,0x02)

	def ioconSetup(self, byteVal):
		"""Set the input or output mode for a specified pin.  Mode should be
		either GPIO.OUT or GPIO.IN.
		"""
		self._device.write8(self.IOCON, byteVal)

	def iocon_pin(self, pin, value):
		"""Set the input or output mode for a specified pin.  Mode should be
		either GPIO.OUT or GPIO.IN.
		"""
		self._validate_pin(pin)
		# Set bit to 1 for input or 0 for output.
		if value == GPIO.IN:
			self.iocon[int(pin/8)] |= 1 << (int(pin%8))
		elif value == GPIO.OUT:
			self.iocon[int(pin/8)] &= ~(1 << (int(pin%8)))
		else:
			raise ValueError('Unexpected value.  Must be GPIO.IN or GPIO.OUT.')
		self.write_iocon()

	def defval_pin(self, pin, value):
		"""Set the input or output mode for a specified pin.  Mode should be
		either GPIO.OUT or GPIO.IN.
		"""
		self._validate_pin(pin)
		# Set bit to 1 for input or 0 for output.
		if value == 1:
			self.defval[int(pin/8)] |= 1 << (int(pin%8))
		elif value == 0:
			self.defval[int(pin/8)] &= ~(1 << (int(pin%8)))
		else:
			raise ValueError('Unexpected value.  Must be GPIO.IN or GPIO.OUT.')
		self.write_defval()

	def intcon_pin(self, pin, value):
		"""Set the input or output mode for a specified pin.  Mode should be
		either GPIO.OUT or GPIO.IN.
		"""
		self._validate_pin(pin)
		# Set bit to 1 for input or 0 for output.
		if value == GPIO.IN:
			self.intcon[int(pin/8)] |= 1 << (int(pin%8))
		elif value == GPIO.OUT:
			self.intcon[int(pin/8)] &= ~(1 << (int(pin%8)))
		else:
			raise ValueError('Unexpected value.  Must be GPIO.IN or GPIO.OUT.')
		self.write_intcon()

	def output(self, pin, value):
		"""Set the specified pin the provided high/low value.  Value should be
		either GPIO.HIGH/GPIO.LOW or a boolean (True = HIGH).
		"""
		self.output_pins({pin: value})

	def output_pins(self, pins):
		"""Set multiple pins high or low at once.  Pins should be a dict of pin
		name to pin value (HIGH/True for 1, LOW/False for 0).  All provided pins
		will be set to the given values.
		"""
		[self._validate_pin(pin) for pin in pins.keys()]
		# Set each changed pin's bit.
		for pin, value in iter(pins.items()):
			if value:
				self.gpio[int(pin/8)] |= 1 << (int(pin%8))
			else:
				self.gpio[int(pin/8)] &= ~(1 << (int(pin%8)))
		# Write GPIO state.
		self.write_gpio()

	def input(self, pin):
		"""Read the specified pin and return GPIO.HIGH/True if the pin is pulled
		high, or GPIO.LOW/False if pulled low.
		"""
		return self.input_pins([pin])[0]

	def input_pins(self, pins):
		"""Read multiple pins specified in the given list and return list of pin values
		GPIO.HIGH/True if the pin is pulled high, or GPIO.LOW/False if pulled low.
		"""
		[self._validate_pin(pin) for pin in pins]
		# Get GPIO state.
		gpio = self._device.readList(self.GPIO, self.gpio_bytes)
		# Return True if pin's bit is set.
		return [(gpio[int(pin/8)] & 1 << (int(pin%8))) > 0 for pin in pins]

	def interrupt(self, pin):
		"""Read the specified pin and return GPIO.HIGH/True if the pin is pulled
		high, or GPIO.LOW/False if pulled low.
		"""
		return self.interrupt_pins([pin])[0]

	def interrupt_pins(self, pins):
		"""Read multiple pins specified in the given list and return list of pin values
		GPIO.HIGH/True if the pin is pulled high, or GPIO.LOW/False if pulled low.
		"""
		[self._validate_pin(pin) for pin in pins]
		# Get GPIO state.
		intflag = self._device.readList(self.INTFA, self.gpio_bytes)
		# Return True if pin's bit is set.
		return [(intflag[int(pin/8)] & 1 << (int(pin%8))) > 0 for pin in pins]

	def readIntRegister(self, bank):
		assert (bank == 0 or bank == 1),"bank must be 0 or 1"
		if bank:
			interruptByte = self._device.readU8(self.INTFB)
		else:
			interruptByte = self._device.readU8(self.INTFA)
		return interruptByte

	def interruptCapture_byte(self, bank):
		assert (bank == 0 or bank == 1),"bank must be 0 or 1"
		if bank:
			interruptCapByte = self._device.readU8(self.INTCAPB)
		else:
			interruptCapByte = self._device.readU8(self.INTCAPA)
		return interruptCapByte

	def interruptCapture(self, pin):
		"""Read the specified pin and return GPIO.HIGH/True if the pin is pulled
		high, or GPIO.LOW/False if pulled low.
		"""
		return self.interruptCapture_pins([pin])[0]

	def interruptCapture_pins(self, pins):
		"""Read multiple pins specified in the given list and return list of pin values
		GPIO.HIGH/True if the pin is pulled high, or GPIO.LOW/False if pulled low.
		"""
		[self._validate_pin(pin) for pin in pins]
		# Get GPIO state.
		intcap = self._device.readList(self.INTCAPA, self.gpio_bytes)
		# Return True if pin's bit is set.
		return [(intcap[int(pin/8)] & 1 << (int(pin%8))) > 0 for pin in pins]

	def outputLatch(self, pin):
		"""Read the specified pin and return GPIO.HIGH/True if the pin is pulled
		high, or GPIO.LOW/False if pulled low.
		"""
		return self.outputLatch_pins([pin])[0]

	def outputLatch_pins(self, pins):
		"""Read multiple pins specified in the given list and return list of pin values
		GPIO.HIGH/True if the pin is pulled high, or GPIO.LOW/False if pulled low.
		"""
		[self._validate_pin(pin) for pin in pins]
		# Get GPIO state.
		outLat = self._device.readList(self.OLATA, self.gpio_bytes)
		# Return True if pin's bit is set.
		return [(outLat[int(pin/8)] & 1 << (int(pin%8))) > 0 for pin in pins]

	def pullup(self, pin, enabled):
		"""Turn on the pull-up resistor for the specified pin if enabled is True,
		otherwise turn off the pull-up resistor.
		"""
		self._validate_pin(pin)
		if enabled:
			self.gppu[int(pin/8)] |= 1 << (int(pin%8))
		else:
			self.gppu[int(pin/8)] &= ~(1 << (int(pin%8)))
		self.write_gppu()

	def write_gpio(self, gpio=None):
		"""Write the specified byte value to the GPIO registor.  If no value
		specified the current buffered value will be written.
		"""
		if gpio is not None:
			self.gpio = gpio
		self._device.writeList(self.GPIO, self.gpio)

	def write_iodir(self, iodir=None):
		"""Write the specified byte value to the IODIR registor.  If no value
		specified the current buffered value will be written.
		"""
		if iodir is not None:
			self.iodir = iodir
		self._device.writeList(self.IODIR, self.iodir)

	def write_gppu(self, gppu=None):
		"""Write the specified byte value to the GPPU registor.  If no value
		specified the current buffered value will be written.
		"""
		if gppu is not None:
			self.gppu = gppu
		self._device.writeList(self.GPPU, self.gppu)
		
	def writegppua(self, gppu_a=None):
		"""Write the specified byte value to the GPPUA registor.  If no value
		specified the current buffered value will be written.
		"""
		if gppu_a is not None:
			self.gppuA = gppuA
		self._device.writeList(self.GPPUA, self.gppu_a)

	def writegppub(self, gppu_b=None):
		"""Write the specified byte value to the GPPUB registor.  If no value
		specified the current buffered value will be written.
		"""
		if gppu_b is not None:
			self.gppu_b = gppu_b
		self._device.writeList(self.GPPUB, self.gppu_b)

	def write_gpinten(self, gpinten=None):
		"""Write the specified byte value to the GPINTEN registor.  If no value
		specified the current buffered value will be written.
		"""
		if gpinten is not None:
			self.gpinten = gpinten
		self._device.writeList(self.GPINTENA, self.gpinten)

	def write_inputPolarity(self, inputPolarity=None):
		"""Write the specified byte value to the IPOL registor.  If no value
		specified the current buffered value will be written.
		"""
		if inputPolarity is not None:
			self.inputPolarity = inputPolarity
		self._device.writeList(self.IPOLA, self.inputPolarity)

	def write_defval(self, defval=None):
		"""Write the specified byte value to the DEFVAL registor.  If no value
		specified the current buffered value will be written.
		"""
		if defval is not None:
			self.defval = defval
		self._device.writeList(self.DEFVALA, self.defval)

	def write_intcon(self, intcon=None):
		"""Write the specified byte value to the INTCON registor.  If no value
		specified the current buffered value will be written.
		"""
		if intcon is not None:
			self.intcon = intcon
		self._device.writeList(self.INTCONA, self.intcon)

	def write_iocon(self, iocon=None):
		"""Write the specified byte value to the IOCON registor.  If no value
		specified the current buffered value will be written.
		"""
		if iocon is not None:
			self.iocon = iocon 
		self._device.writeList(self.IOCON, self.iocon)

class MCP23017(MCP230xxBase):
	"""MCP23017-based GPIO class with 16 GPIO pins."""
	# Define number of pins and registor addresses.
	NUM_GPIO = 16
	IODIR = 0x00
	GPIO = 0x12
	GPPU = 0x0C
	IODIRA = 0x00
	IODIRB = 0x01
	IPOLA = 0x02
	IPOLB = 0x03
	GPINTENA = 0x04
	GPINTENB = 0x05
	DEFVALA = 0x06
	DEFVALB = 0x07
	INTCONA = 0x08
	INTCONB = 0x09
	IOCON = 0x0A
	GPPUA = 0x0C
	GPPUB = 0x0D
	INTFA = 0x0E
	INTFB = 0x0F
	INTCAPA = 0x10
	INTCAPB = 0x11
	GPIOA = 0x12
	GPIOB = 0x13
	OLATA = 0x14
	OLATB = 0x15

	def __init__(self, address=0x20, **kwargs):
		super(MCP23017, self).__init__(address, **kwargs)