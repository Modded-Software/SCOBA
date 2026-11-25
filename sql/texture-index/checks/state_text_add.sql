-- Host test: keep a state text as the tooling keeps one, named by no field yet.
INSERT INTO text (key, body, uses) VALUES (?, ?, 0) ON CONFLICT (key) DO NOTHING
