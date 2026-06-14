# database.py
import sqlite3
from datetime import datetime

DB_NAME = "lise.db"

def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        username TEXT,
        full_name TEXT,
        join_date TEXT,
        balance INTEGER DEFAULT 0,
        is_banned INTEGER DEFAULT 0
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS services (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        volume INTEGER,
        months INTEGER,
        total_price INTEGER,
        start_date TEXT,
        end_date TEXT,
        config TEXT,
        status TEXT
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS transactions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        amount INTEGER,
        method TEXT,
        tracking_code TEXT,
        status TEXT,
        created_at TEXT
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY,
        value TEXT
    )''')
    c.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('welcome_photo', '')")
    c.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('welcome_text', 'به فروشگاه Lise خوش آمدید')")
    conn.commit()
    conn.close()

def get_user(user_id):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    user = c.fetchone()
    conn.close()
    return user

def add_user(user_id, username, full_name):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO users (user_id, username, full_name, join_date) VALUES (?, ?, ?, ?)",
              (user_id, username, full_name, datetime.now()))
    conn.commit()
    conn.close()

def update_balance(user_id, amount):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (amount, user_id))
    conn.commit()
    conn.close()

def add_transaction(user_id, amount, method, tracking_code, status):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("INSERT INTO transactions (user_id, amount, method, tracking_code, status, created_at) VALUES (?, ?, ?, ?, ?, ?)",
              (user_id, amount, method, tracking_code, status, datetime.now()))
    conn.commit()
    conn.close()

def add_service(user_id, volume, months, total_price, status):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("INSERT INTO services (user_id, volume, months, total_price, status) VALUES (?, ?, ?, ?, ?)",
              (user_id, volume, months, total_price, status))
    conn.commit()
    return c.lastrowid

def get_pending_transactions():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT * FROM transactions WHERE status = 'pending' ORDER BY created_at DESC")
    rows = c.fetchall()
    conn.close()
    return rows

def confirm_transaction(tx_id):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("UPDATE transactions SET status = 'confirmed' WHERE id = ?", (tx_id,))
    conn.commit()
    conn.close()