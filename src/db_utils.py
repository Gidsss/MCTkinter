import sqlite3
from datetime import datetime
import logging

# Set up logging configuration
logging.basicConfig(level=logging.INFO, format='[%(asctime)s] %(levelname)s - %(message)s')

DB_PATH = "steganography.db"

def init_db():
    """Initialize the database and create the file_history table if it doesn't exist."""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS file_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_name TEXT,
                algorithm TEXT,
                operation TEXT,
                timestamp TEXT,
                encoded_text TEXT
            )
        ''')
        conn.commit()
        conn.close()
        logging.info("Database initialized successfully.")
    except Exception as e:
        logging.error(f"Error initializing database: {e}")

def save_file_record(file_name, algorithm, operation, encoded_text):
    """Save a record of encoded/decoded files."""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute('''
            INSERT INTO file_history (file_name, algorithm, operation, timestamp, encoded_text)
            VALUES (?, ?, ?, ?, ?)
        ''', (file_name, algorithm, operation, timestamp, encoded_text))
        conn.commit()
        conn.close()
        logging.info(f"Record saved: {file_name} ({operation}) using {algorithm}")
    except Exception as e:
        logging.error(f"Error saving file record: {e}")

def get_all_files():
    """Retrieve all file records from the database."""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute('SELECT id, file_name, algorithm, operation, timestamp, encoded_text FROM file_history')
        rows = cursor.fetchall()
        conn.close()
        logging.info(f"Retrieved {len(rows)} file records from the database.")
        return rows
    except Exception as e:
        logging.error(f"Error retrieving file records: {e}")
        return []

def get_encoded_text(file_name, operation="encode"):
    """Retrieve encoded text for a specific file from the database."""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute('''
            SELECT encoded_text FROM file_history
            WHERE file_name = ? AND operation = ?
            ORDER BY timestamp DESC LIMIT 1
        ''', (file_name, operation))
        result = cursor.fetchone()
        conn.close()

        if result:
            logging.info(f"Encoded text retrieved for file: {file_name}")
            return result[0]
        else:
            logging.warning(f"No encoded text found for file: {file_name}")
            return None
    except Exception as e:
        logging.error(f"Error retrieving encoded text: {e}")
        return None
