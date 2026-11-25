-- Host test: a text is named by the state field of every texture row more.
UPDATE text SET uses = uses + (SELECT COUNT(*) FROM texture) WHERE id = ?
