-- Host test: each text whose count is not the number of fields naming it: id, count, fields.
SELECT t.id, t.uses, COUNT(f.id) FROM text t
LEFT JOIN (
    SELECT listed AS id FROM texture
    UNION ALL SELECT description FROM texture
    UNION ALL SELECT state FROM texture
    UNION ALL SELECT description FROM owner
    UNION ALL SELECT state FROM owner
) f ON f.id = t.id
GROUP BY t.id HAVING t.uses != COUNT(f.id)
