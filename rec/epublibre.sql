CREATE TABLE IF NOT EXISTS EPUB (
    id INTEGER PRIMARY KEY,
    title TEXT NOT NULL,
    description TEXT,
    simply_title TEXT NOT NULL,
    simply_author TEXT NOT NULL,
    author TEXT,
    language TEXT
);

CREATE INDEX IF NOT EXISTS idx_epub_language
    ON EPUB(language);

CREATE VIRTUAL TABLE IF NOT EXISTS EPUB_FTS USING fts5(
    simply_title,
    simply_author,
    content='EPUB',
    content_rowid='id',
    tokenize='trigram'
);

CREATE TRIGGER IF NOT EXISTS epub_fts_insert AFTER INSERT ON EPUB BEGIN
    INSERT INTO EPUB_FTS(rowid, simply_title, simply_author)
    VALUES (new.id, new.simply_title, new.simply_author);
END;

CREATE TRIGGER IF NOT EXISTS epub_fts_delete AFTER DELETE ON EPUB BEGIN
    INSERT INTO EPUB_FTS(EPUB_FTS, rowid, simply_title, simply_author)
    VALUES ('delete', old.id, old.simply_title, old.simply_author);
END;

CREATE TRIGGER IF NOT EXISTS epub_fts_update AFTER UPDATE ON EPUB BEGIN
    INSERT INTO EPUB_FTS(EPUB_FTS, rowid, simply_title, simply_author)
    VALUES ('delete', old.id, old.simply_title, old.simply_author);
    INSERT INTO EPUB_FTS(rowid, simply_title, simply_author)
    VALUES (new.id, new.simply_title, new.simply_author);
END;