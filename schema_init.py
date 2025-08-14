import sqlite3, os, json, datetime
from config import DB_PATH, DATA_DIR

os.makedirs(DATA_DIR, exist_ok=True)

def init():
    fresh = not os.path.exists(DB_PATH)
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    c.execute("""CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nickname TEXT UNIQUE,
        team TEXT,
        role TEXT,
        points INTEGER DEFAULT 0,
        joined_at TEXT
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS attendance (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nickname TEXT,
        session_name TEXT,
        timestamp TEXT
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS polls (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        question TEXT,
        options TEXT,   -- JSON list
        votes TEXT      -- JSON dict: { "0": int, "1": int, ... }
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS uploads (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        filename TEXT,
        uploader TEXT,
        ts TEXT
    )""")

    if fresh:
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        c.executemany(
            "INSERT INTO users (nickname, team, role, points, joined_at) VALUES (?,?,?,?,?)",
            [
                ("Soumyasri", "girls", "student", 10, now),
                ("Ravi", "boys", "student", 8, now),
                ("Priya", "girls", "student", 6, now),
                ("Arun", "boys", "student", 5, now),
            ],
        )
        c.execute(
            "INSERT INTO polls (question, options, votes) VALUES (?,?,?)",
            ("After class plan?",
             json.dumps(["Go canteen", "Group study"]),
             json.dumps({"0": 1, "1": 2}))
        )

    conn.commit()
    conn.close()
    print("✅ Database ready at:", DB_PATH)

if __name__ == "__main__":
    init()

