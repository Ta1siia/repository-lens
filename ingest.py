from concurrent.futures import ThreadPoolExecutor, as_completed

from db import get_connection, get_or_create_repo, commit_exists, write_commit, update_last_synced, init_db
from github import github_pagination, fetch_commit_detail


def ingest_repo(owner, name):
    con = get_connection()
    repo_id = get_or_create_repo(con, owner, name)
    shas = github_pagination(owner, name)
    # Skip commits already in the DB — makes repeat ingests of a repo
    # that's only gained a few new commits fast instead of full re-fetch.
    unknown_shas = [sha for sha in shas if not commit_exists(con, sha)]

    #fetch concurrently (I/O-bound, safe to parallelize),
    # then write sequentially (SQLite allows only one writer at a time).
    # Threads below only call the GitHub API — none of them touch `con`.
    results = []
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = {executor.submit(fetch_commit_detail, owner, name, sha): sha for sha in unknown_shas}
        for future in as_completed(futures):
            sha = futures[future]
            try:
                results.append(future.result())
            except Exception as e:
                # One bad commit shouldn't abort the whole ingest 
                print(f"Skipping commit {sha}: {e}")

    for result in results:
        write_commit(con, result, repo_id)

    if shas:
        update_last_synced(con, repo_id, shas[0])

    con.close()