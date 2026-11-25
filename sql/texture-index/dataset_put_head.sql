-- A dataset's head. A new row has no origins yet; an old one keeps them.
INSERT INTO dataset (game, dataset, head, origins) VALUES (?, ?, ?, '')
ON CONFLICT (game, dataset) DO UPDATE SET head = excluded.head
