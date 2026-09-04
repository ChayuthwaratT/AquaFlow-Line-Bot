import sqlite3

DB_FILE = "bot.db"

def get_connection():
    return sqlite3.connect(DB_FILE)

def init_db():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            line_user_id TEXT PRIMARY KEY,
            meter_number TEXT NOT NULL,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS pending_verifications (
            line_user_id TEXT PRIMARY KEY,
            meter_number TEXT NOT NULL,
            resident_name TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()

def get_meter_number(line_user_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT meter_number FROM users WHERE line_user_id = ?", (line_user_id,))
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else None

def save_meter_number(line_user_id, meter_number):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO users (line_user_id, meter_number, updated_at)
        VALUES (?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(line_user_id) DO UPDATE SET
            meter_number = excluded.meter_number,
            updated_at = CURRENT_TIMESTAMP
    """, (line_user_id, meter_number))
    conn.commit()
    conn.close()

def delete_meter_number(line_user_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM users WHERE line_user_id = ?", (line_user_id,))
    conn.commit()
    conn.close()

def save_pending(line_user_id, meter_number, resident_name):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO pending_verifications (line_user_id, meter_number, resident_name, created_at)
        VALUES (?, ?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(line_user_id) DO UPDATE SET
            meter_number = excluded.meter_number,
            resident_name = excluded.resident_name,
            created_at = CURRENT_TIMESTAMP
    """, (line_user_id, meter_number, resident_name))
    conn.commit()
    conn.close()

def get_pending(line_user_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT meter_number, resident_name FROM pending_verifications WHERE line_user_id = ?", (line_user_id,))
    row = cursor.fetchone()
    conn.close()
    return {"meter_number": row[0], "resident_name": row[1]} if row else None

def clear_pending(line_user_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM pending_verifications WHERE line_user_id = ?", (line_user_id,))
    conn.commit()
    conn.close()
