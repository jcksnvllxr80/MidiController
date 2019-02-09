import xml.etree.ElementTree as ET
import DoublyLinkedList

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
		inside the XML file that describes the particular list
		'''
		self._setlist_name = value



	def load_setlist(self, setlist_path):
		'''read and load the setlist. calls the getsongnames method and then calls the loadsong method
		'''
		self.get_song_names(setlist_path)
		for song_name in self.song_list:
			self.load_song(song_name)

	def get_song_names(self, setlist_path): #get songs from xml, put in List
		'''method for reading the setlist and appending song names to a list
		'''
		setlist_file = ET.parse(setlist_path +'.xml')
		setlist_root = setlist_file.getroot()
		self.setlist_name = setlist_root.get('name')
		for song in setlist_root.iter('song'):
			self.song_list.append(song.get("name"))

	def load_song(self, song_name): 
		'''gets song names from list and then opens each individual song
		file from the song directory and reads it into memory.
		'''
		song_file = ET.parse("/home/pi/Looper/PartSongSet/Songs/" + song_name + '.xml')     
		song_root = song_file.getroot()    #get the root of the song xml file     
		tempo = song_root.find('tempo').text #get the tempo of the song
		new_song = Song(song_name, tempo)  #create a new song object
		for part in song_root.iter('part'): #iterate the song xml over each part
			part_name = part.get("name") #get the name of the part
			new_part = Part(part_name)   #create a new part object 
			for pedal in part.iter('pedal'): #iterate all the pedals for each part
				pedal_name = pedal.get("name") #store pedal name, whether its on or off, 
				engaged = bool(pedal.find("./engaged").text) #and if it has a setting associated with it 
				setting = pedal.find('setting')
				if setting is not None: 
					setting = setting.text
				new_part.add_pedal(pedal_name, engaged, setting) #add each pedal to a dictionary of pedals       
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
