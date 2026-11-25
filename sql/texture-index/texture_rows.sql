-- Every texture row of a dataset, with the text of each text field.
SELECT x.dataset, l.body, d.body, s.body FROM texture x
JOIN text l ON l.id = x.listed JOIN text d ON d.id = x.description JOIN text s ON s.id = x.state
WHERE x.game = ? AND x.dataset = ?
