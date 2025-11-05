# services/models.py
import sqlite3
import hashlib
import os
import secrets 

# Configuration for the database file
DATABASE_DIR = os.path.join(os.path.abspath(os.path.dirname(os.path.dirname(__file__))), 'instance')
DATABASE_PATH = os.path.join(DATABASE_DIR, 'gen_study.db')

def get_db():
    """Returns a new database connection."""
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row 
    return conn

def init_db():
    """Initializes the database and creates the necessary tables."""
    os.makedirs(DATABASE_DIR, exist_ok=True)
    conn = get_db()
    cursor = conn.cursor()
    
    # 1. Users Table (for login/roles/xp)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL,
            xp INTEGER DEFAULT 0
        )
    ''')

    # 2. Scores Table (for teacher monitoring)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS scores (
            id INTEGER PRIMARY KEY,
            user_id INTEGER NOT NULL,
            topic TEXT NOT NULL,
            score_percentage REAL NOT NULL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')
    conn.commit()
    conn.close()

# --- User Management Functions (Non-ORM) ---

def hash_password(password):
    """Hashes password using SHA-256 for basic security."""
    return hashlib.sha256(password.encode()).hexdigest()

def get_user_by_id(user_id):
    """Retrieves a user record by ID (used by Flask-Login)."""
    conn = get_db()
    # Ensure user_id is treated as an integer for the query
    user = conn.execute('SELECT * FROM users WHERE id = ?', (int(user_id),)).fetchone()
    conn.close()
    return user

def get_user_by_username(username):
    """Retrieves a user record by username."""
    conn = get_db()
    user = conn.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()
    conn.close()
    return user

def create_user(username, password, role='student'):
    """Adds a new user to the database."""
    conn = get_db()
    hashed_pass = hash_password(password)
    try:
        conn.execute('INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)',
                     (username, hashed_pass, role))
        conn.commit()
        conn.close()
        return True
    except sqlite3.IntegrityError:
        conn.close()
        return False

class User:
    """A simple class wrapper to satisfy Flask-Login requirements."""
    def __init__(self, user_data):
        self.id = user_data['id']
        self.username = user_data['username']
        self.password_hash = user_data['password_hash']
        self.role = user_data['role']
        self.xp = user_data['xp']

    def is_active(self):
        return True
    
    def is_authenticated(self):
        return True

    def is_anonymous(self):
        return False

    def get_id(self):
        return str(self.id)
    
    def check_password(self, password):
        return self.password_hash == hash_password(password)