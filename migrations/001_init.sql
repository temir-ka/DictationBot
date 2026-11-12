-- Схема БД. Даты хранятся ISO-строками (YYYY-MM-DD).

CREATE TABLE users (
    id                  INTEGER PRIMARY KEY,                -- telegram user_id
    current_streak      INTEGER NOT NULL DEFAULT 0,
    best_streak         INTEGER NOT NULL DEFAULT 0,
    last_completed_at   TEXT,
    reminder_time       TEXT    NOT NULL,                   -- HH:MM
    last_measurement_at TEXT
);

-- Белый список: бот отвечает только тем, кого добавил владелец.
CREATE TABLE allowed_users (
    id       INTEGER PRIMARY KEY,                           -- telegram user_id
    name     TEXT,                                          -- имя и @username на момент добавления
    added_at TEXT    NOT NULL
);

-- Выполненные сеты. Блоки 1-4 фиксированы, меняется только абзац для чтения.
CREATE TABLE completions (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id         INTEGER NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    date            TEXT    NOT NULL,
    reading_text_id TEXT    NOT NULL,
    UNIQUE (user_id, date)
);

CREATE TABLE measurements (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id         INTEGER NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    date            TEXT    NOT NULL,
    control_text_id TEXT    NOT NULL,
    voice_file_id   TEXT    NOT NULL,
    notes           TEXT
);

CREATE INDEX idx_measurements_user ON measurements (user_id, id);
