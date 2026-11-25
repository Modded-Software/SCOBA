-- Host test: a file of another schema. The caller sets user_version above the index's SCHEMA.
CREATE TABLE texture (junk TEXT);
CREATE TABLE other (junk TEXT);
