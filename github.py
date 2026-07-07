import os
import requests
from dotenv import load_dotenv


BASE_URL = 'https://api.github.com/'
MAX_COMMITS = 400
load_dotenv()


def github_get(url):
    headers = {
    'Authorization': f'Bearer {os.getenv("GITHUB_PAT")}',
    'Accept': 'application/vnd.github+json',
    'X-GitHub-Api-Version': '2026-03-10',
    }
    return requests.get(url, headers=headers)


def github_pagination(owner, name):
    url = f"{BASE_URL}repos/{owner}/{name}/commits?per_page=100"
    shas = []
    while True:
        r = github_get(url)
        shas.extend(c["sha"] for c in r.json())
        if len(shas) >= MAX_COMMITS:
            break
        next_url = r.links.get("next")
        if next_url is None:
            break
        url = next_url["url"]
    return shas


def fetch_commit_detail(owner, name, sha):
    url = f"{BASE_URL}repos/{owner}/{name}/commits/{sha}"
    r = github_get(url)
    data = r.json()
    result = {
        "sha": data["sha"],
        "message": data["commit"]["message"],
        "author": data["commit"]["author"]["name"],
        "committed_at": data["commit"]["committer"]["date"],
        "files": [
            {
                "filename": f["filename"],
                "additions": f["additions"],
                "deletions": f["deletions"],
                "previous_filename": f.get("previous_filename")
            }
            for f in data["files"]
        ]
    }
    return result
