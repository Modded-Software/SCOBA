-- One more field names a kept text: its id. No row: the text is not kept yet.
UPDATE text SET uses = uses + 1 WHERE key = ? RETURNING id
