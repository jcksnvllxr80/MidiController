from ez_setup import use_setuptools
use_setuptools()
from setuptools import setup, find_packages

setup(name 				= 'Looper',
	  version 			= '1.0.0',
	  author			= 'Aaron Watkins',
	  author_email		= 'ac.watkins80@gmail.com',
	  description		= 'Looper Pedal with presets and MIDI.',
	  license			= 'MIT',
	  packages 			= find_packages())
