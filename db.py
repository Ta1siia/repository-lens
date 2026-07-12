import sqlite3
from datetime import datetime, timezone

DB_PATH = "db/repolens.db"

def get_connection():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    return con

def write_commit(con, result, repo_id):
    con.execute(
        "INSERT INTO commits (sha, repo_id, message, author, committed_at) VALUES (?, ?, ?, ?, ?)",
        (result["sha"], repo_id, result["message"], result["author"], result["committed_at"]),
    )
    for f in result["files"]:
        con.execute(
            "INSERT INTO commit_files (commit_sha, previous_filename, filename, additions, deletions) VALUES (?, ?, ?, ?, ?)",
            (result["sha"], f["previous_filename"], f["filename"], f["additions"], f["deletions"]),
        )
    con.commit()

def commit_exists(con, sha):
    return con.execute("SELECT 1 FROM commits WHERE sha = ? LIMIT 1", (sha,)).fetchone() is not None

def get_or_create_repo(con, owner, name):
    existing = con.execute(
        "SELECT id FROM repos WHERE owner = ? AND name = ?", (owner, name)
    ).fetchone()
    if existing is not None:
        return existing["id"]
    new_id = con.execute(
        "INSERT INTO repos (owner, name) VALUES (?, ?)", (owner, name)
    ).lastrowid
    con.commit()
    return new_id

def update_last_synced(con, repo_id, sha):
    con.execute(
        "UPDATE repos SET last_synced_sha = ?, last_synced_at = ? WHERE id = ?",
        (sha, datetime.now(timezone.utc).isoformat(), repo_id),
    )
    con.commit()

def get_last_synced(con, repo_id):
    row = con.execute("SELECT last_synced_sha FROM repos WHERE id = ?", (repo_id,)).fetchone()
    return row["last_synced_sha"] if row is not None else None

def get_commit_files(con, repo_id):
    return con.execute(
        """
        SELECT commit_files.commit_sha, commit_files.previous_filename, commit_files.filename
        FROM commit_files
        JOIN commits ON commit_files.commit_sha = commits.sha
        WHERE commits.repo_id = ?
        ORDER BY commit_files.commit_sha
        """,
        (repo_id,),
    ).fetchall()

def get_recent_commits_for_file(con, repo_id, filename, limit=10):
    return con.execute(
        """
        SELECT commits.sha, commits.message, commits.author, commits.committed_at
        FROM commits
        JOIN commit_files ON commit_files.commit_sha = commits.sha
        WHERE commit_files.filename = ? AND commits.repo_id = ?
        ORDER BY commits.committed_at DESC
        LIMIT ?
        """,
        (filename, repo_id, limit),
    ).fetchall()

def init_db():
    con = get_connection()
    with open("db/schema.sql") as file:
        schema_sql = file.read()
    con.executescript(schema_sql)
    con.commit()
    con.close()
