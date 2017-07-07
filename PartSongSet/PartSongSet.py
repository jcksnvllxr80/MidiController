import xml.etree.ElementTree as ET
import DoublyLinkedList

class Setlist(object):
	'''class for importing, editing, and maintaining a setlist. 
	'''
	def __init__(self):
		self.songs = DoublyLinkedList.DoublyLinkedList()  #create an empty list for keeping multiple Song objects
		self.songList = [] #create an empty list for keeping song names that correspond to the setlist songs
		
	def setSetlistName(self, setlistName):
		'''method for stetting the setlist name according to "name" attribute"
		inside the XML file that describes the particular list
		'''
		self.setlistName = setlistName

	def getSetlistName(self):
		'''return the name of the setlist
		'''
		return self.setlistName

	def loadSetlist(self, setlistPath):
		'''read and load the setlist. calls the getsongnames method and then calls the loadsong method
		'''
		self.getSongNames(setlistPath)
		for songName in self.songList:
			self.loadSong(songName)

	def getSongNames(self, setlistPath): #get songs from xml, put in List
		'''method for reading the setlist and appending song names to a list
		'''
		setlistFile = ET.parse(setlistPath +'.xml')
		setlistRoot = setlistFile.getroot()
		self.setSetlistName(setlistRoot.get('name'))
		for song in setlistRoot.iter('song'):
			self.songList.append(song.get("name"))

	def loadSong(self, songName): 
		'''gets song names from list and then opens each individual song
		file from the song directory and reads it into memory.
		'''
		songFile = ET.parse("/home/pi/Looper/PartSongSet/Songs/" + songName + '.xml')     
		songRoot = songFile.getroot()    #get the root of the song xml file     
		tempo = songRoot.find('tempo').text #get the tempo of the song
		newSong = Song(songName, tempo)  #create a new song object
		for part in songRoot.iter('part'): #iterate the song xml over each part
			partName = part.get("name") #get the name of the part
			newPart = Part(partName)   #create a new part object 
			for pedal in part.iter('pedal'): #iterate all the pedals for each part
				pedalName = pedal.get("name") #store pedal name, whether its on or off, 
				engaged = bool(pedal.find("./engaged").text) #and if it has a setting associated with it 
				setting = pedal.find('setting')
				if setting is not None: 
					setting = setting.text
				newPart.addPedal(pedalName, engaged, setting) #add each pedal to a dictionary of pedals       
			newSong.addPart(newPart) #add part to the "parts" doublyLinkedList in Song   
		self.songs.append(newSong) #add song to the "songs" doublyLinkedList in Setlist


class Song(object):
	'''class "has-a" a doubly linked list of parts, "is-a" object
	methods are 'addPart' and 'getTempo'.
	'''
	def __init__(self, name, bpm):
		self.parts = DoublyLinkedList.DoublyLinkedList() 
		self.name = name
		self.bpm = bpm
        
	def addPart(self, newPart, i=None):
		'''method calls the doublylinkedlist obect 'parts' to append
		or insert a new part depending on 'i'
		'''
		if i is None:
			self.parts.append(newPart)
		elif i >= 0:
			self.parts.insert(newPart, i)
	
	def getTempo(self):
		'''returns the tempo for the song object that called 'getTempo'
		'''
		return self.bpm


class Part(object):
	'''part class has a 'name' property, holds each pedal and its tuple of (engaged, setting)
	in a dictionary 'PedalDictionary'. Its methods are add pedal and 'IsEngaged'
	'''
	def __init__(self, partName):
		self.partName = partName
		self.PedalDictionary = {}

	def addPedal(self, pedalName, engaged, setting):
		'''adds a pedal to the dict
		'''
		self.PedalDictionary[pedalName] = (engaged, setting)
