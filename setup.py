from ez_setup import use_setuptools

use_setuptools()
from setuptools import setup, find_packages

setup(name='MidiController',
      version='1.0.2',
      author='Aaron Watkins',
      author_email='ac.watkins80@gmail.com',
      description='MIDI Controller Pedal.',
      license='MIT',
      packages=find_packages())
