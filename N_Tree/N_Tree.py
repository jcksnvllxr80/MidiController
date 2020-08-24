class Node(object):
    
    def __init__(self, name=None, func=None, menu_data_func=None, parent=None):
        self.name = name
        self.parent = parent
        self.current_child = None
        self.children = []
        self.func = func
        self.menu_data_prompt = None
        self.menu_data_items = []
        self.menu_data_dict = {}
        self.menu_data_position = None
        self.menu_data_func = menu_data_func
        self.menu_data_loaded = False

    def add_child(self, name, func=None, menu_data_func=None):
        # adds a child to the list of children for a given Node
        if self.current_child is None:
            self.current_child = 0
        child = Node(name, func, menu_data_func, self)
        self.children.append(child)
        return child

    def remove_child(self, child):
        # pass the child object to be removed from the list
        self.children.remove(child)


class N_Tree(object):

    def __init__(self, root):
        self.root = Node(root)
        self.current_node = self.root
