CREATE TABLE repos (
    id INTEGER PRIMARY KEY,
    owner TEXT NOT NULL,
    name TEXT NOT NULL,
    last_synced_sha TEXT,
    last_synced_at TEXT,
    UNIQUE(owner, name)
) STRICT;

CREATE TABLE commits (
    sha TEXT PRIMARY KEY,
    repo_id INTEGER NOT NULL,
    message TEXT,
    author TEXT,
    committed_at TEXT,
    FOREIGN KEY (repo_id) REFERENCES repos(id)
) STRICT;

CREATE TABLE commit_files (
    id INTEGER PRIMARY KEY,
    commit_sha TEXT NOT NULL,
    previous_filename TEXT,
    filename TEXT NOT NULL,
    additions INTEGER,
    deletions INTEGER,
    FOREIGN KEY (commit_sha) REFERENCES commits(sha)
) STRICT;

CREATE TABLE summaries (
    commit_sha TEXT,
    repo_id INTEGER NOT NULL,
    filename TEXT NOT NULL,
    summary TEXT,
    generated_at TEXT,
    PRIMARY KEY (repo_id, filename),
    FOREIGN KEY (repo_id) REFERENCES repos(id)
) STRICT;