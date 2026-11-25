-- The owner rows of a dataset whose ids the JSON array names.
SELECT x.owner, d.body, s.body FROM owner x
JOIN text d ON d.id = x.description JOIN text s ON s.id = x.state
WHERE x.game = ? AND x.dataset = ? AND x.owner IN (SELECT value FROM json_each(?))
