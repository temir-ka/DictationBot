-- Начальная схема. Даты хранятся ISO-строками (YYYY-MM-DD), списки — JSON.

CREATE TABLE users (
    id                  INTEGER PRIMARY KEY,                -- telegram user_id
    current_streak      INTEGER NOT NULL DEFAULT 0,
    best_streak         INTEGER NOT NULL DEFAULT 0,
    last_completed_at   TEXT,
    reminder_time       TEXT    NOT NULL,                   -- HH:MM
    last_measurement_at TEXT
);

CREATE TABLE completions (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id         INTEGER NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    date            TEXT    NOT NULL,
    exercise_ids    TEXT    NOT NULL,                       -- JSON: 4 упражнения дня
    twister_id      TEXT    NOT NULL,
    reading_text_id TEXT    NOT NULL,
    UNIQUE (user_id, date)
);

CREATE TABLE measurements (
    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id               INTEGER NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    date                  TEXT    NOT NULL,
    control_text_id       TEXT    NOT NULL,
    twister_ids           TEXT    NOT NULL,                 -- JSON-список id
    voice_precise_file_id TEXT    NOT NULL,
    voice_casual_file_id  TEXT    NOT NULL,
    notes                 TEXT
);

CREATE INDEX idx_measurements_user ON measurements (user_id, id);
