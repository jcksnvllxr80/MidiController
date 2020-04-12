import yaml
import DoublyLinkedList
import logging

SONG_PATH = "/home/pi/MidiController/PartSongSet/Songs/"

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
formatter = logging.Formatter("%(asctime)s [PartSongSet.py] [%(levelname)-5.5s]  %(message)s")
handler.setFormatter(formatter)
logger.addHandler(handler)



class Setlist(object):
	'''class for importing, editing, and maintaining a setlist. 
	'''
	def __init__(self):
		self.songs = DoublyLinkedList.DoublyLinkedList()  #create an empty list for keeping multiple Song objects
		self.song_list = [] #create an empty list for keeping song names that correspond to the setlist songs


	@property
	def setlist_name(self):
		'''return the name of the setlist
		'''
		return self._setlist_name


	@setlist_name.setter
	def setlist_name(self, value):
		'''method for setting the setlist name according to "name" attribute"
		inside the yaml file that describes the particular list
		'''
		self._setlist_name = value


	def read_config(self, config_file):
		# read config yaml file into dictionaries
		with open(config_file, 'r') as ymlfile:
			config_dict = yaml.full_load(ymlfile)
		return config_dict


	def load_setlist(self, setlist_path):
		'''read and load the setlist. calls the getsongnames method and then calls the loadsong method
		'''
		logger.info("set setlist to: " + setlist_path)
		self.get_song_names(setlist_path)
		for song_name in self.song_list:
			self.load_song(song_name)


	def get_song_names(self, setlist_path): #get songs from yaml, put in List
		'''method for reading the setlist and appending song names to a list
		'''
		setlist_dict = self.read_config(setlist_path +'.yaml')
		self.setlist_name = setlist_dict['name']
		[self.song_list.append(song) for song in setlist_dict['songs']]


	def load_song(self, song_name): 
		'''gets song names from list and then opens each individual song
		file from the song directory and reads it into memory.
		'''
		logger.info("set song to: " + song_name) 
		song_dict = self.read_config(SONG_PATH + song_name + '.yaml')      
		tempo = song_dict['tempo'] #get the tempo of the song
		new_song = Song(song_name, tempo)  #create a new song object
		parts = song_dict['parts']
		for part_name, part in parts: #iterate the song yaml over each part
			new_part = Part(part_name)   #create a new part object 
			for pedal_name, pedal in part['pedals']: #iterate all the pedals for each part
				engaged = bool(pedal['engaged']) #and if it has a setting associated with it 
				preset = pedal.get('preset', '')
				new_part.add_pedal(pedal_name, engaged, preset) #add each pedal to a dictionary of pedals       
			new_song.add_part(new_part) #add part to the "parts" doublyLinkedList in Song   
		self.songs.append(new_song) #add song to the "songs" doublyLinkedList in Setlist


class Song(object):
	'''class "has-a" a doubly linked list of parts, "is-a" object
	methods are 'add_part' and 'get_tempo'.
	'''
	def __init__(self, name, bpm):
		self.parts = DoublyLinkedList.DoublyLinkedList() 
		self.name = name
		self.bpm = bpm
        
	def add_part(self, new_part, i=None):
		'''method calls the doublylinkedlist obect 'parts' to append
		or insert a new part depending on 'i'
		'''
		if i is None:
			self.parts.append(new_part)
		elif i >= 0:
			self.parts.insert(new_part, i)
	
	def get_tempo(self):
		'''returns the tempo for the song object that called 'get_tempo'
		'''
		return self.bpm


class Part(object):
	'''part class has a 'name' property, holds each pedal and its tuple of (engaged, setting)
	in a dictionary 'pedal_dictionary'. Its methods are add pedal and 'IsEngaged'
	'''
	def __init__(self, part_name):
		self.part_name = part_name
		self.pedal_dictionary = {}

	def add_pedal(self, pedal_name, engaged, setting):
		'''adds a pedal to the dict
		'''
		self.pedal_dictionary[pedal_name] = (engaged, setting)