import config
import database
from classes import ChatNode
from nicegui import app

class SessionState:
    def __init__(self):
        self.root = ChatNode("system", "Start of Conversation")
        self.current_node = self.root
        self.user = None 
        self.total_input = 0
        self.total_output = 0
        self.total_cost = 0.0
        self.selected_model_key = config.DEFAULT_MODEL_KEY

    def initialize_from_storage(self):
        """Checks if a user is logged in via browser storage and restores state."""
        if app.storage.user.get('email'):
            email = app.storage.user.get('email')
            cost = database.get_user_cost(email)
            self.user = {"email": email, "total_cost": cost}
            self.total_cost = cost