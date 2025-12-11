import sqlite3
import hashlib

DB_NAME = "chat_users.db"

def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            email TEXT PRIMARY KEY,
            password_hash TEXT,
            total_cost REAL DEFAULT 0.0
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS conversations (
            id TEXT PRIMARY KEY,
            email TEXT,
            title TEXT,
            tree_data TEXT,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def create_user(email, password):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    try:
        c.execute("INSERT INTO users (email, password_hash, total_cost) VALUES (?, ?, 0.0)", 
                  (email, hash_password(password)))
        conn.commit()
        success = True
    except sqlite3.IntegrityError:
        success = False
    finally:
        conn.close()
    return success

def authenticate_user(email, password):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT email, total_cost FROM users WHERE email = ? AND password_hash = ?", 
              (email, hash_password(password)))
    row = c.fetchone()
    conn.close()
    if row:
        return {"email": row[0], "total_cost": row[1]}
    return None

def update_user_cost(email, cost_increment):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("UPDATE users SET total_cost = total_cost + ? WHERE email = ?", (cost_increment, email))
    conn.commit()
    conn.close()

def get_user_cost(email):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT total_cost FROM users WHERE email = ?", (email,))
    row = c.fetchone()
    conn.close()
    return row[0] if row else 0.0

import json
from classes import ChatNode

def save_conversation(email, root_node):
    if not email: return
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    
    # Generate a title from the first user message if possible
    title = "New Conversation"
    if root_node.children:
        # DFS to find first user node
        stack = [root_node]
        while stack:
            curr = stack.pop(0)
            if curr.role == "user":
                title = curr.content[:50] + "..."
                break
            stack = list(curr.children) + stack # Check children
            
    tree_data = json.dumps(root_node.to_dict())
    
    c.execute('''
        INSERT OR REPLACE INTO conversations (id, email, title, tree_data, updated_at)
        VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
    ''', (root_node.id, email, title, tree_data))
    
    conn.commit()
    conn.close()

def get_user_conversations(email):
    if not email: return []
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT id, title, updated_at FROM conversations WHERE email = ? ORDER BY updated_at DESC", (email,))
    rows = c.fetchall()
    conn.close()
    return rows

def load_conversation(conversation_id):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT tree_data FROM conversations WHERE id = ?", (conversation_id,))
    row = c.fetchone()
    conn.close()
    
    if row:
        data = json.loads(row[0])
        return ChatNode.from_dict(data)
    return None