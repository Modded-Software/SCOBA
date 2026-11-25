-- What was read of an original, and the size and time of its file then.
SELECT sha256, longest, unreadable, bytes, changed FROM original WHERE game = ? AND origin = ?
