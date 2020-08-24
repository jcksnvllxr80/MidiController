class Node(object):

	def __init__(self, data, prev, next):
		self.data = data
		self.prev = prev
		self.next = next


class DoublyLinkedList(object):

	def __init__(self) : 
		self.length = 0 
		self.head = None
		self.tail = None

	def append(self, data):
		new_node = Node(data, None, None)
		if self.head is None:
			self.head = self.tail = new_node
		else:
			new_node.prev = self.tail
			new_node.next = None
			self.tail.next = new_node
			self.tail = new_node
		self.length += 1

	def prepend(self, data):
		new_head = Node(data).next
		new_head.next = self.head
		self.head = new_head

	def insert(self, data, position):
		if position == 0 or not self.head:
			self.prepend(data)
		else:
			node_to_insert = Node(data)
			iter_node = self.head
			pos = position
			while pos > 1 and iter_node.next:
				iter_node = iter_node.next
				pos -= 1
			node_to_insert.next = iter_node.next
			iter_node.next = node_to_insert

	def remove(self, node_value):
		current_node = self.head
		while node_value is not None:
			if current_node.data == node_value:
				# if it's not the first element
				if current_node.prev is not None:
					current_node.prev.next = current_node.next
					current_node.next.prev = current_node.prev
				else:
					# otherwise we have no prev, head is the next one, and prev becomes None
					self.head = current_node.next
					current_node.next.prev = None
			current_node = current_node.next
		self.length -= 1

	def show(self):
		print("Show list data:")
		current_node = self.head
		while current_node is not None:
			print (current_node.data)
			current_node = current_node.next
		print("*"*50)

	def to_list(self):
		data_list = []
		current_node = self.head
		while current_node is not None:
			data_list.append(current_node.data)
			current_node = current_node.next
		return data_list

	def index_to_node(self, index):
		node = self.head
		for i in range(1, index):
			if node.next is not None:
				node = node.next
		return node

	def node_to_index(self, node):
		temp_node = self.head
		index = None
		for i in range(1, self.length + 1):
			if node is not temp_node:
				if temp_node.next is not None:
					temp_node = temp_node.next
			else:
				index = i
				break
		return index

	def get_length(self):
		return self.length

	def get_head(self):
		return self.head

	def get_tail(self):
		return self.tail
