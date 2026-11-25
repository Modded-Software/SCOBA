-- One texture row, new or in place of the old one.
INSERT OR REPLACE INTO texture (game, dataset, asset, origin, kind, listed, description, state)
VALUES (?, ?, ?, ?, ?, ?, ?, ?)
