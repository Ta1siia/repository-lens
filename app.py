from urllib.parse import urlparse

from flask import Flask, request, jsonify, render_template
from requests.exceptions import HTTPError

from db import get_connection, get_or_create_repo, get_last_synced, get_recent_commits_for_file, get_summary, save_summary, init_db
from github import get_head_sha
from ingest import ingest_repo
from analysis import build_graph
from summarize import summarize_commits

app = Flask(__name__)
init_db()


def parse_github_url(url):
    url = url.strip()
    if not url:
        raise ValueError("URL is empty")

    if "://" not in url:
        url = "https://" + url if "github.com" in url else "https://github.com/" + url

    parsed = urlparse(url)
    if parsed.netloc.lower() != "github.com":
        raise ValueError(f"unsupported host: {parsed.netloc or url}")
    segments = [s for s in parsed.path.split("/") if s]
    if len(segments) < 2:
        raise ValueError("URL must include an owner and a repo name")
    owner, name = segments[0], segments[1]

    if name.endswith(".git"):
        name = name[:-4]
    owner, name = owner.strip(), name.strip()
    if not owner or not name:
        raise ValueError("owner/name cannot be empty")

    return owner, name


@app.route("/graph", methods=["POST"])
def graph_route():
    data = request.get_json(silent=True) or {}
    url = data.get("url")
    if not url:
        return jsonify({"error": "url is required"}), 400

    try:
        owner, name = parse_github_url(url)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    con = get_connection()
    try:
        repo_id = get_or_create_repo(con, owner, name)

        try:
            head_sha = get_head_sha(owner, name)
            last_synced = get_last_synced(con, repo_id)
            if last_synced is None or head_sha != last_synced:
                ingest_repo(owner, name)
        except HTTPError as e:
            status = e.response.status_code if e.response is not None else 502
            message = "repo not found" if status == 404 else f"GitHub error: {status}"
            return jsonify({"error": message}), status

        graph = build_graph(con, repo_id)
    finally:
        con.close()

    return jsonify(graph)

@app.route("/commits", methods=["POST"])
def commits_route():
    data = request.get_json(silent=True) or {}
    url = data.get("url")
    filename = data.get("filename")
    if not url or not filename:
        return jsonify({"error": "url and filename are required"}), 400

    try:
        owner, name = parse_github_url(url)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    con = get_connection()
    try:
        repo_id = get_or_create_repo(con, owner, name)
        commits = get_recent_commits_for_file(con, repo_id, filename)
    finally:
        con.close()

    return jsonify([dict(row) for row in commits])

@app.route("/summary", methods=["POST"])
def summary_route():
    data = request.get_json(silent=True) or {}
    url = data.get("url")
    filename = data.get("filename")
    if not url or not filename:
        return jsonify({"error": "url and filename are required"}), 400

    try:
        owner, name = parse_github_url(url)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    con = get_connection()
    try:
        repo_id = get_or_create_repo(con, owner, name)
        commits = get_recent_commits_for_file(con, repo_id, filename)
        if not commits:
            return jsonify({"summary": "No history for this file yet."})

        sha = commits[0]["sha"]
        cached = get_summary(con, repo_id, filename)
        if cached is not None and cached["commit_sha"] == sha:
            return jsonify({"summary": cached["summary"]})

        messages = [c["message"] for c in commits]
        try:
            summary = summarize_commits(messages)
        except Exception:
            return jsonify({"error": "summary generation is temporarily unavailable"}), 502

        save_summary(con, repo_id, filename, sha, summary)
    finally:
        con.close()

    return jsonify({"summary": summary})

@app.route("/")
def index():
    return render_template("index.html")