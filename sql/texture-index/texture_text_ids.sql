-- The text ids of one texture row, for their release.
SELECT listed, description, state FROM texture WHERE game = ? AND dataset = ? AND asset = ?
