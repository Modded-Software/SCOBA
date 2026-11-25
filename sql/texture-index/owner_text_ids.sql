-- The text ids of one owner row, for their release.
SELECT description, state FROM owner WHERE game = ? AND dataset = ? AND owner = ?
