class Node(object):
    
    def __init__(self, name=None, func=None, parent=None):
        self.name = name
        self.parent = parent
        self.func = func
        self.children = []
 

    def add_child(self, name, func=None):
        # adds a child to the list of children for a given Node
        child = Node(name, func, self)
        self.children.append(child)
        return child

    
    def remove_child(self, child):
        # pass the child object to be removed from the list
        self.children.remove(child)


class N_Tree(object):

    def __init__(self, root):
        self.root = Node(root)
        self.current_node = self.root
