CREATE TABLE IF NOT EXISTS btc_lobbies (code TEXT PRIMARY KEY, state TEXT NOT NULL, revision INTEGER NOT NULL DEFAULT 0, expires INTEGER NOT NULL);
CREATE INDEX IF NOT EXISTS btc_lobbies_expiry ON btc_lobbies(expires);
CREATE TABLE IF NOT EXISTS btc_admission (key TEXT PRIMARY KEY, hits INTEGER NOT NULL, expires INTEGER NOT NULL);
CREATE INDEX IF NOT EXISTS btc_admission_expiry ON btc_admission(expires);
