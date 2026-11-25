-- The viewer's reader: the state of one texture.
SELECT s.body AS state FROM texture x JOIN text s ON s.id = x.state
WHERE x.game = ? AND x.dataset = ? AND x.asset = ?
