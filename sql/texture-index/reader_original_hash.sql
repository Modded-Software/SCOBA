-- The viewer's reader: the hash of an original's file, as the pipeline last read it.
SELECT sha256 FROM original WHERE game = ? AND origin = ?
