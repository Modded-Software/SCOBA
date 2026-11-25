-- Where one texture file of a dataset lies (the pipeline and the viewer's reader).
SELECT origin FROM origin WHERE game = ? AND dataset = ? AND asset = ?
