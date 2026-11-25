-- Every texture row of a dataset of one kind.
SELECT x.dataset, l.body, d.body, s.body FROM texture x
JOIN text l ON l.id = x.listed JOIN text d ON d.id = x.description JOIN text s ON s.id = x.state
WHERE x.game = ? AND x.dataset = ? AND x.kind = ? ORDER BY x.asset
