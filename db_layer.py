import sqlite3
import os

# 📂 База хранится в папке data/
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_DIR = os.path.join(BASE_DIR, "data")
os.makedirs(DB_DIR, exist_ok=True)

DB_PATH = os.path.join(DB_DIR, "progress.db")


def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    # Основная таблица пользователей
    c.execute(
        """CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            current_day INTEGER DEFAULT 0,
            is_finished INTEGER DEFAULT 0,
            hard_mode INTEGER DEFAULT 0,
            last_task_given INTEGER DEFAULT 0,
            started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )"""
    )

    # Прогресс по дням
    c.execute(
        """CREATE TABLE IF NOT EXISTS progress (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            day INTEGER,
            description TEXT,
            completed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES users(user_id)
        )"""
    )
    conn.commit()

    # 🔄 Миграция: проверяем наличие нужных колонок и добавляем, если их нет
    migrate_add_column_if_missing(conn, "users", "hard_mode", "INTEGER DEFAULT 0")
    migrate_add_column_if_missing(conn, "users", "last_task_given", "INTEGER DEFAULT 0")

    conn.close()


def migrate_add_column_if_missing(conn: sqlite3.Connection, table: str, column: str, col_type: str):
    """Проверяет наличие колонки и добавляет её, если нет"""
    cur = conn.cursor()
    cur.execute(f"PRAGMA table_info({table})")
    columns = [row[1] for row in cur.fetchall()]
    if column not in columns:
        print(f"⚙️ Миграция: добавляем колонку {column} в {table}")
        cur.execute(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}")
        conn.commit()


def get_user(user_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "SELECT user_id, current_day, is_finished, hard_mode, last_task_given FROM users WHERE user_id=?",
        (user_id,),
    )
    row = c.fetchone()
    conn.close()
    return row


def create_user(user_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "INSERT OR IGNORE INTO users (user_id, current_day, is_finished, hard_mode, last_task_given) VALUES (?, 0, 0, 0, 0)",
        (user_id,),
    )
    conn.commit()
    conn.close()


def update_user_day(user_id, day):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("UPDATE users SET current_day=? WHERE user_id=?", (day, user_id))
    conn.commit()
    conn.close()


def finish_user(user_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("UPDATE users SET is_finished=1 WHERE user_id=?", (user_id,))
    conn.commit()
    conn.close()


def reset_user(user_id, hard_mode=False):
    """Сброс прогресса (для новой игры)"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "UPDATE users SET current_day=0, is_finished=0, hard_mode=?, last_task_given=0 WHERE user_id=?",
        (1 if hard_mode else 0, user_id),
    )
    conn.commit()
    conn.close()

    # Удаляем старый прогресс
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("DELETE FROM progress WHERE user_id=?", (user_id,))
    conn.commit()
    conn.close()


def save_progress(user_id, day, text):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "INSERT INTO progress (user_id, day, description) VALUES (?, ?, ?)",
        (user_id, day, text),
    )
    conn.commit()
    conn.close()


def get_progress(user_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "SELECT day, description FROM progress WHERE user_id=? ORDER BY day",
        (user_id,),
    )
    rows = c.fetchall()
    conn.close()
    return rows


def set_task_given(user_id, given: bool):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "UPDATE users SET last_task_given=? WHERE user_id=?",
        (1 if given else 0, user_id),
    )
    conn.commit()
    conn.close()


def was_task_given(user_id) -> bool:
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT last_task_given FROM users WHERE user_id=?", (user_id,))
    row = c.fetchone()
    conn.close()
    return bool(row[0]) if row else False
