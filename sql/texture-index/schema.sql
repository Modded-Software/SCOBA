-- The tables of the state index (scripts/hdtex/core/index.py, SCHEMA).
-- listed, description and state of a texture row, and description and state
-- of an owner row, are ids of `text`. Each statement is run on its own.
CREATE TABLE dataset (
    game TEXT NOT NULL, dataset TEXT NOT NULL, head TEXT NOT NULL, origins TEXT NOT NULL,
    PRIMARY KEY (game, dataset)) WITHOUT ROWID;
CREATE TABLE text (
    id INTEGER PRIMARY KEY, key BLOB NOT NULL UNIQUE, body BLOB NOT NULL, uses INTEGER NOT NULL);
CREATE TABLE texture (
    game TEXT NOT NULL, dataset TEXT NOT NULL, asset TEXT NOT NULL, origin TEXT NOT NULL, kind TEXT NOT NULL,
    listed INTEGER NOT NULL, description INTEGER NOT NULL, state INTEGER NOT NULL,
    PRIMARY KEY (game, dataset, asset)) WITHOUT ROWID;
CREATE INDEX texture_origin ON texture (game, origin);
CREATE INDEX texture_kind ON texture (game, dataset, kind);
CREATE TABLE original (
    game TEXT NOT NULL, origin TEXT NOT NULL, sha256 TEXT NOT NULL, longest INTEGER NOT NULL, unreadable TEXT NOT NULL,
    bytes INTEGER NOT NULL, changed INTEGER NOT NULL,
    PRIMARY KEY (game, origin)) WITHOUT ROWID;
CREATE TABLE origin (
    game TEXT NOT NULL, dataset TEXT NOT NULL, asset TEXT NOT NULL, origin TEXT NOT NULL,
    PRIMARY KEY (game, dataset, asset)) WITHOUT ROWID;
CREATE TABLE owner (
    game TEXT NOT NULL, dataset TEXT NOT NULL, owner TEXT NOT NULL, description INTEGER NOT NULL, state INTEGER NOT NULL,
    PRIMARY KEY (game, dataset, owner)) WITHOUT ROWID;
