import sqlite3
from cryptography.fernet import Fernet
import os

class Database:
    def __init__(self, db_file):
        self.conn = sqlite3.connect(db_file)
        self.cursor = self.conn.cursor()
        
        # Check if the table exists and has the correct schema
        self.cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users'")
        table_exists = self.cursor.fetchone() is not None

        if not table_exists:
            # Create the table if it doesn't exist
            self.cursor.execute('''
                CREATE TABLE users (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT,
                    encrypted_password TEXT
                )
            ''')
        else:
            # Check if the encrypted_password column exists
            self.cursor.execute("PRAGMA table_info(users)")
            columns = [column[1] for column in self.cursor.fetchall()]
            if 'encrypted_password' not in columns:
                # Alter the table to add the encrypted_password column
                self.cursor.execute('ALTER TABLE users ADD COLUMN encrypted_password TEXT')
        
        self.conn.commit()
        
        # Generate or load encryption key
        if not os.path.exists('encryption_key.key'):
            self.key = Fernet.generate_key()
            with open('encryption_key.key', 'wb') as key_file:
                key_file.write(self.key)
        else:
            with open('encryption_key.key', 'rb') as key_file:
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
        return [(user_id, username, self.cipher_suite.decrypt(encrypted_password.encode()).decode()) 
                for user_id, username, encrypted_password in users]

    def remove_all_users(self):
        self.cursor.execute('DELETE FROM users')
        self.conn.commit()

    def close(self):
        self.conn.close()

    def user_exists(self, user_id):
        self.cursor.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
        return self.cursor.fetchone() is not None
