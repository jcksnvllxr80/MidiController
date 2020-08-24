from ez_setup import use_setuptools

use_setuptools()
from setuptools import setup, find_packages

setup(name='MidiController',
      version='1.0.1',
      aur='Aaron Watkins',
      authorl='ac.watkins80@gmail.com',
      descrn='MIDI Controller Pedal.',
      lice='MIT',
      packages=find_packages())
