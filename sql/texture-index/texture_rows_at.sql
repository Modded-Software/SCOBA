-- Every texture row, of every dataset, whose original lies at an origin.
SELECT x.dataset, l.body, d.body, s.body FROM texture x
JOIN text l ON l.id = x.listed JOIN text d ON d.id = x.description JOIN text s ON s.id = x.state
WHERE x.game = ? AND x.origin = ? ORDER BY x.dataset, x.asset
