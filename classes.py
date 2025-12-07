import uuid
from google.genai import types

class ChatNode:
    def __init__(self, role, content, parent=None):
        self.id = str(uuid.uuid4())[:8]
        self.role = role
        self.content = content
        self.parent = parent
        self.children = []
        self.timestamp = str(uuid.uuid1())

    def add_child(self, node):
        self.children.append(node)
        return node

    def get_history(self):
        history = []
        nodes = []
        current = self
        while current:
            history.insert(0, types.Content(
                role=current.role,
                parts=[types.Part(text=current.content)]
            ))
            nodes.insert(0, current)
            current = current.parent
        return history, nodes

    def get_question_label(self):
        if self.role != "user": return None
        prefix = ""
        ancestor = self.parent
        while ancestor:
            if ancestor.role == "user":
                prefix = ancestor.get_question_label()
                break
            ancestor = ancestor.parent
        
        if self.parent:
            siblings = [child for child in self.parent.children if child.role == "user"]
            try:
                my_index = siblings.index(self) + 1
            except ValueError:
                my_index = 1
        else:
            my_index = 1

        if prefix: return f"{prefix}.{my_index}"
        else: return str(my_index)

    # --- NEW: DRAG & DROP SUPPORT ---
    def reorder_children(self, new_indices):
        """
        Reorders the children list based on a list of indices.
        args:
            new_indices: A list of integers representing the new order of the current children.
        """
        if not self.children: return
        
        # Create a map of current children
        current_children = {i: child for i, child in enumerate(self.children)}
        
        new_list = []
        for idx in new_indices:
            if idx in current_children:
                new_list.append(current_children[idx])
        
        # Ensure we didn't lose any (safety check)
        if len(new_list) == len(self.children):
            self.children = new_list