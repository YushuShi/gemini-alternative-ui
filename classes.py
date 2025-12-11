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

    def remove_child(self, node):
        if node in self.children:
            self.children.remove(node)
            return True
        return False

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

    def to_dict(self):
        return {
            "id": self.id,
            "role": self.role,
            "content": self.content,
            "children": [child.to_dict() for child in self.children],
            "timestamp": self.timestamp
        }

    @classmethod
    def from_dict(cls, data, parent=None):
        node = cls(data["role"], data["content"], parent)
        node.id = data["id"]
        node.timestamp = data.get("timestamp", str(uuid.uuid1()))
        for child_data in data.get("children", []):
            node.children.append(cls.from_dict(child_data, node))
        return node

    def find_node(self, target_id):
        if self.id == target_id:
            return self
        for child in self.children:
            found = child.find_node(target_id)
            if found: return found
        return None