from db import get_connection, get_or_create_repo, commit_exists, write_commit, update_last_synced, init_db
from github import github_pagination, fetch_commit_detail


def ingest_repo(owner, name):
    con = get_connection()
    repo_id = get_or_create_repo(con, owner, name)
    shas = github_pagination(owner, name)

    for sha in shas:
        if commit_exists(con, sha):
            continue
        try:
            result = fetch_commit_detail(owner, name, sha)
            write_commit(con, result, repo_id)
        except Exception as e:
            print(f"Skipping commit {sha}: {e}")
            continue

    if shas:
        update_last_synced(con, repo_id, shas[0])

    con.close()

if __name__ == "__main__":
    init_db()
    ingest_repo("octocat", "Hello-World")