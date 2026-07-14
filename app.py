import threading
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

# Tracks in-flight/completed ingests, keyed by (owner, name). Only correct
# with a single gunicorn worker — a second worker process would have its own
# copy of this dict and the lock below wouldn't guard anything across them.
# Entries are never evicted (one per distinct repo ever visited) — an
# intentional simplification, not an oversight, given expected traffic.
_jobs = {}
_jobs_lock = threading.Lock()


def _run_ingest_job(owner, name):
    key = (owner, name)
    try:
        ingest_repo(owner, name)
        with _jobs_lock:
            _jobs[key] = {"status": "done"}
    except Exception as e:
        with _jobs_lock:
            _jobs[key] = {"status": "error", "error": str(e)}


def parse_github_url(url):
    url = url.strip()
    if not url:
        raise ValueError("URL is empty")

    if "://" not in url:
        # Accept both bare "owner/repo" and "github.com/owner/repo" —
        # only prefix the host if it's missing too.
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
        except HTTPError as e:
            status = e.response.status_code if e.response is not None else 502
            message = "repo not found" if status == 404 else f"GitHub error: {status}"
            return jsonify({"error": message}), status

        # Only re-ingest if the repo's HEAD moved since last sync — this is
        # what makes repeat visits fast (cache hit, synchronous response).
        last_synced = get_last_synced(con, repo_id)
        if last_synced is not None and head_sha == last_synced:
            graph = build_graph(con, repo_id)
            return jsonify(graph)

        # Cache miss: kick off ingest in the background instead of blocking
        # this request, unless a job for this repo is already running.
        key = (owner, name)
        with _jobs_lock:
            job = _jobs.get(key)
            if job is None or job["status"] != "running":
                _jobs[key] = {"status": "running"}
                threading.Thread(target=_run_ingest_job, args=(owner, name), daemon=True).start()

        return jsonify({"status": "ingesting"}), 202
    finally:
        con.close()

@app.route("/graph/status", methods=["POST"])
def graph_status_route():
    data = request.get_json(silent=True) or {}
    url = data.get("url")
    if not url:
        return jsonify({"error": "url is required"}), 400

    try:
        owner, name = parse_github_url(url)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    with _jobs_lock:
        job = _jobs.get((owner, name))
    status = job["status"] if job is not None else "done"

    if status == "running":
        return jsonify({"status": "ingesting"}), 202
    if status == "error":
        return jsonify({"status": "error", "error": job.get("error", "ingest failed")}), 500

    con = get_connection()
    try:
        repo_id = get_or_create_repo(con, owner, name)
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
            # Don't call the LLM on an empty file history.
            return jsonify({"summary": "No history for this file yet."})

        sha = commits[0]["sha"]
        cached = get_summary(con, repo_id, filename)
        # Cache is valid only if the file hasn't changed since it was generated —
        # comparing sha, not just checking "does a summary exist."
        if cached is not None and cached["commit_sha"] == sha:
            return jsonify({"summary": cached["summary"]})

        messages = [c["message"] for c in commits]
        try:
            summary = summarize_commits(messages)
        except Exception:
            # Gemini call can fail (due to quota or network) — degrade gracefully
            # instead of a raw 500.
            return jsonify({"error": "summary generation is temporarily unavailable"}), 502

        save_summary(con, repo_id, filename, sha, summary)
    finally:
        con.close()

    return jsonify({"summary": summary})

@app.route("/")
def index():
    return render_template("index.html")