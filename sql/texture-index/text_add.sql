-- A new text, named by one field: its id.
INSERT INTO text (key, body, uses) VALUES (?, ?, 1) RETURNING id
