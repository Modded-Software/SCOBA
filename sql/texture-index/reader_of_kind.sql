-- The viewer's reader: the description and state of every texture of one kind.
SELECT d.body AS description, s.body AS state FROM texture x
JOIN text d ON d.id = x.description JOIN text s ON s.id = x.state
WHERE x.game = ? AND x.dataset = ? AND x.kind = ? ORDER BY x.asset
