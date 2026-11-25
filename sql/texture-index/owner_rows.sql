-- Every owner row of a dataset, with the text of each text field.
SELECT x.owner, d.body, s.body FROM owner x
JOIN text d ON d.id = x.description JOIN text s ON s.id = x.state
WHERE x.game = ? AND x.dataset = ?
