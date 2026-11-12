-- Вечернее напоминание («стрик под угрозой»): HH:MM, NULL — выключено.
ALTER TABLE users ADD COLUMN evening_time TEXT DEFAULT '21:00';

-- Состояние диалогов (замер, смена времени): переживает перезапуск бота.
CREATE TABLE fsm (
    key   TEXT PRIMARY KEY,                                 -- bot:chat:user:thread:business:destiny
    state TEXT,
    data  TEXT NOT NULL DEFAULT '{}'                        -- JSON
);
