-- Белый список: бот отвечает только тем, кого добавил владелец.

CREATE TABLE allowed_users (
    id       INTEGER PRIMARY KEY,                           -- telegram user_id
    name     TEXT,                                          -- имя и @username на момент добавления
    added_at TEXT    NOT NULL
);

-- До белого списка зарегистрироваться мог только владелец — доступ у него сохраняется.
INSERT INTO allowed_users (id, added_at) SELECT id, date('now') FROM users;
