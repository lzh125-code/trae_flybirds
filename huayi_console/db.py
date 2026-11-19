# -*- coding: utf-8 -*-
"""控制台持久层：SQLite 初始化与事件/任务读写。

每个函数独立开连接，避免多线程共享连接（守护读日志与请求线程会并发写事件）。
"""
import sqlite3
import time
from pathlib import Path

DB_PATH = Path(__file__).with_name("console.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_name TEXT DEFAULT '',
    lesson_index INTEGER DEFAULT 0,
    lesson_name TEXT DEFAULT '',
    status TEXT DEFAULT 'running',
    duration INTEGER DEFAULT 0,
    played INTEGER DEFAULT 0,
    segment INTEGER DEFAULT -1,
    started_at TEXT DEFAULT '',
    ended_at TEXT DEFAULT ''
);
CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id INTEGER,
    ts REAL NOT NULL,
    kind TEXT DEFAULT '日志',
    level TEXT DEFAULT 'info',
    message TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS answers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    question TEXT NOT NULL,
    options TEXT DEFAULT '',
    correct TEXT DEFAULT '',
    source TEXT DEFAULT '',
    hits INTEGER DEFAULT 0,
    updated_at TEXT DEFAULT ''
);
CREATE TABLE IF NOT EXISTS exam_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id INTEGER,
    questions TEXT DEFAULT '',
    source TEXT DEFAULT '',
    score INTEGER DEFAULT 0,
    result TEXT DEFAULT '',
    duration INTEGER DEFAULT 0,
    created_at TEXT DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_events_id ON events(id);
"""


def connect():
    conn = sqlite3.connect(DB_PATH, timeout=15)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with connect() as conn:
        conn.executescript(SCHEMA)
        conn.execute("PRAGMA journal_mode=WAL")


def add_event(message, kind="日志", level="info", task_id=None):
    with connect() as conn:
        cursor = conn.execute(
            "INSERT INTO events (task_id, ts, kind, level, message) VALUES (?, ?, ?, ?, ?)",
            (task_id, time.time(), kind, level, message),
        )
        return cursor.lastrowid


def recent_events(after_id=0, limit=200):
    with connect() as conn:
        rows = conn.execute(
            "SELECT id, task_id, ts, kind, level, message FROM events "
            "WHERE id > ? ORDER BY id ASC LIMIT ?",
            (after_id, limit),
        ).fetchall()
    return [dict(row) for row in rows]


def tail_events(limit=200):
    with connect() as conn:
        rows = conn.execute(
            "SELECT id, task_id, ts, kind, level, message FROM events "
            "ORDER BY id DESC LIMIT ?", (limit,),
        ).fetchall()
    return [dict(row) for row in reversed(rows)]


def create_task(project_name, lesson_index, lesson_name, duration):
    started_at = time.strftime("%Y-%m-%d %H:%M:%S")
    with connect() as conn:
        cursor = conn.execute(
            "INSERT INTO tasks (project_name, lesson_index, lesson_name, status, duration, started_at) "
            "VALUES (?, ?, ?, 'running', ?, ?)",
            (project_name, lesson_index, lesson_name, duration, started_at),
        )
        return cursor.lastrowid


def update_task(task_id, **fields):
    if not task_id or not fields:
        return
    columns = ", ".join("%s = ?" % key for key in fields)
    with connect() as conn:
        conn.execute("UPDATE tasks SET %s WHERE id = ?" % columns,
                     list(fields.values()) + [task_id])


def last_task_id():
    with connect() as conn:
        row = conn.execute("SELECT id FROM tasks ORDER BY id DESC LIMIT 1").fetchone()
    return row["id"] if row else None
