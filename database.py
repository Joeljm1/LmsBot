import sqlite3
from cryptography.fernet import Fernet
import os

class Database:
    """
    Handles all database operations including user management and credential encryption.
    Uses SQLite for storage and Fernet for encryption.
    """
    
    def __init__(self, db_file):
       
        # Initialize database connection
        self.conn = sqlite3.connect(db_file)
        self.cursor = self.conn.cursor()
        
        # Check and create database structure if needed
        self._initialize_database()
        
        # Setup encryption
        self._setup_encryption()

    def _initialize_database(self):
        # Check if users table exists
        self.cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='users'"
        )
        table_exists = self.cursor.fetchone() is not None

        if not table_exists:
            # Create new users table
            self._create_users_table()
        else:
            # Verify and update existing table structure
            self._verify_table_structure()
        
        self.conn.commit()

    def _create_users_table(self):
        self.cursor.execute('''
            CREATE TABLE users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                encrypted_password TEXT
            )
        ''')

    def _verify_table_structure(self):
        """Verify and update table structure if needed."""
        self.cursor.execute("PRAGMA table_info(users)")
        columns = [column[1] for column in self.cursor.fetchall()]
        
        # Add encrypted_password column if it doesn't exist
        if 'encrypted_password' not in columns:
            self.cursor.execute(
                'ALTER TABLE users ADD COLUMN encrypted_password TEXT'
            )

    def _setup_encryption(self):
        """Initialize or load encryption key for password encryption."""
        key_file_path = 'encryption_key.key'
        
        if not os.path.exists(key_file_path):
            # Generate new encryption key
            self.key = Fernet.generate_key()
            with open(key_file_path, 'wb') as key_file:
                key_file.write(self.key)
        else:
            # Load existing encryption key
            with open(key_file_path, 'rb') as key_file:
                self.key = key_file.read()
        
        self.cipher_suite = Fernet(self.key)

    def add_user(self, user_id, username, password):
     
        encrypted_password = self.cipher_suite.encrypt(password.encode()).decode()
        self.cursor.execute('''
            INSERT OR REPLACE INTO users (user_id, username, encrypted_password)
            VALUES (?, ?, ?)
        ''', (user_id, username, encrypted_password))
        self.conn.commit()

    def get_all_users(self):
    
        self.cursor.execute('SELECT user_id, username, encrypted_password FROM users')
        users = self.cursor.fetchall()
        
        # Decrypt passwords before returning
        return [
            (
                user_id, 
                username, 
                self.cipher_suite.decrypt(encrypted_password.encode()).decode()
            ) 
            for user_id, username, encrypted_password in users
        ]

    def remove_all_users(self):
       
        self.cursor.execute('DELETE FROM users')
        self.conn.commit()

    def user_exists(self, user_id):
       
        self.cursor.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
        return self.cursor.fetchone() is not None

    def close(self):
     
        self.conn.close()

    def set_time_window(self, user_id, weeks):
        """Store user's preferred time window for notifications"""
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_preferences (
                user_id INTEGER PRIMARY KEY,
                time_window INTEGER
            )
        ''')
        self.cursor.execute('''
            INSERT OR REPLACE INTO user_preferences (user_id, time_window)
            VALUES (?, ?)
        ''', (user_id, weeks))
        self.conn.commit()

    def get_time_window(self, user_id):
        """Get user's preferred time window (defaults to 2 weeks)"""
        self.cursor.execute('''
            SELECT time_window FROM user_preferences WHERE user_id = ?
        ''', (user_id,))
        result = self.cursor.fetchone()
        return result[0] if result else 2
