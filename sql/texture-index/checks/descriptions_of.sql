-- Host test: how many description texts the rows of one asset name.
SELECT COUNT(DISTINCT description) FROM texture WHERE asset = ?
