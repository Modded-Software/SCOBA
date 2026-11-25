-- The SHA-256 of a dataset's origins, as now written.
UPDATE dataset SET origins = ? WHERE game = ? AND dataset = ?
