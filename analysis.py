from collections import Counter
from itertools import combinations

from db import get_commit_files

MAX_COMMIT_FILES = 10

# AI assistance from Claude: helped understand and resolve renaming problems that would cause fracturing of graph
def build_rename_map(commit_files_rows):
    raw = {}
    for row in commit_files_rows:
        if row["previous_filename"]:
            raw[row["previous_filename"]] = row["filename"]

    def resolve(name):
        # A file can be renamed more than once across its history
        # (A -> B -> C), so walk the chain forward until it stops moving.
        # `seen` guards against a cycle causing an infinite loop.
        seen = set()
        while name in raw and name not in seen:
            seen.add(name)
            name = raw[name]
        return name

    return {old: resolve(old) for old in raw}

# Files with no rename history aren't in the map — return them as-is.
def canonical_name(name, rename_map):
    return rename_map.get(name, name)


def group_by_commit(commit_files_rows):
    commits = {}
    for row in commit_files_rows:
        commits.setdefault(row["commit_sha"], []).append(row)
    return commits


def build_graph(con, repo_id):
    rows = get_commit_files(con, repo_id)
    rename_map = build_rename_map(rows)
    commits = group_by_commit(rows)

    node_counts = Counter()
    edge_counts = Counter()

    for files in commits.values():
        canonical_files = {canonical_name(f["filename"], rename_map) for f in files}

        for name in canonical_files:
            node_counts[name] += 1
        # Large commits (config changes, mass renames, formatting sweeps) touch
        # many unrelated files and would create noisy edges between files that
        # don't actually work together. Node weight still counts every commit —
        # only edges are skipped past this threshold.
        if len(canonical_files) > MAX_COMMIT_FILES:
            continue

        for a, b in combinations(sorted(canonical_files), 2):
            # sorted() makes the pair order deterministic, so (a, b) and (b, a)
            # from different commits count as the same edge.
            edge_counts[(a, b)] += 1

    nodes = [{"file": name, "weight": count} for name, count in node_counts.items()]
    edges = [{"file1": a, "file2": b, "weight": count} for (a, b), count in edge_counts.items()]

    return {"nodes": nodes, "edges": edges}
