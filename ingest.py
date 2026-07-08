from concurrent.futures import ThreadPoolExecutor, as_completed

from db import get_connection, get_or_create_repo, commit_exists, write_commit, update_last_synced, init_db
from github import github_pagination, fetch_commit_detail


def ingest_repo(owner, name):
    con = get_connection()
    repo_id = get_or_create_repo(con, owner, name)
    shas = github_pagination(owner, name)
    unknown_shas = [sha for sha in shas if not commit_exists(con, sha)]

    results = []
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = {executor.submit(fetch_commit_detail, owner, name, sha): sha for sha in unknown_shas}
        for future in as_completed(futures):
            sha = futures[future]
            try:
                results.append(future.result())
            except Exception as e:
                print(f"Skipping commit {sha}: {e}")

    for result in results:
        write_commit(con, result, repo_id)

    if shas:
        update_last_synced(con, repo_id, shas[0])

    con.close()