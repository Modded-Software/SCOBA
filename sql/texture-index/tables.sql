-- The tables of the file, of any schema: a file of another schema is emptied.
SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'
