-- The viewer's reader: the state of one owner.
SELECT s.body AS state FROM owner x JOIN text s ON s.id = x.state
WHERE x.game = ? AND x.dataset = ? AND x.owner = ?
