-- A row: a sync wrote the dataset's origins.
SELECT 1 FROM origin WHERE game = ? AND dataset = ? LIMIT 1
