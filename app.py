"""
Change Impact Workbench — Web Application
==========================================
IBM Bob 2.0 Hackathon — Legacy Retail Co demonstration

Entry point:
    python app.py
    Open: http://127.0.0.1:5000

This app is a guided UI over the existing ciw_engine.py.
It does NOT perform independent analysis; all findings originate from the engine.
Source viewing is restricted to files inside BOB_HT/src/. Uploaded code is never
executed. No connection to a live IBM i or mainframe environment exists.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from flask import Flask, jsonify, render_template, request, abort

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
BASE_DIR = Path(__file__).parent
SIM_DIR  = BASE_DIR / "sim"
SRC_DIR  = BASE_DIR / "src"

# Ensure the sim/ package is importable
sys.path.insert(0, str(SIM_DIR))

import ciw_engine as engine

# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------
app = Flask(__name__, template_folder="templates", static_folder="static")
# Allow small JSON POST bodies (API only). Large uploads are not needed.
app.config["MAX_CONTENT_LENGTH"] = 64 * 1024  # 64 KB ceiling

# ---------------------------------------------------------------------------
# Cached catalog (rebuilt once on startup; refresh via /api/catalog/refresh)
# ---------------------------------------------------------------------------
_catalog_cache: engine.ArtifactCatalog | None = None


def get_catalog() -> engine.ArtifactCatalog:
    global _catalog_cache
    if _catalog_cache is None:
        _catalog_cache = engine.build_catalog(BASE_DIR)
    return _catalog_cache


# ---------------------------------------------------------------------------
# Helper — safe source read (restricted to src/)
# ---------------------------------------------------------------------------
_ALLOWED_EXTENSIONS = {".dds", ".rpgle", ".clp", ".cbl", ".cob", ".cpy"}

def _safe_read_source(rel_path: str, highlight_line: int = 0) -> dict:
    """
    Read a source member from within BOB_HT/src/.
    Returns {lines: [...], highlight_line: n, path: str} or raises 403.
    Any path traversal outside src/ is rejected.
    """
    try:
        resolved = (BASE_DIR / rel_path).resolve()
        src_resolved = SRC_DIR.resolve()
        resolved.relative_to(src_resolved)   # raises ValueError if outside src/
    except (ValueError, Exception):
        abort(403, "Source path outside repository boundary.")

    if resolved.suffix.lower() not in _ALLOWED_EXTENSIONS:
        abort(403, "File type not permitted for source viewing.")

    if not resolved.exists():
        abort(404, f"Source member not found: {rel_path}")

    raw_lines = resolved.read_text(encoding="utf-8", errors="replace").splitlines()
    lines = [{"no": i + 1, "text": ln} for i, ln in enumerate(raw_lines)]
    return {"lines": lines, "highlight_line": highlight_line, "path": rel_path}


# ---------------------------------------------------------------------------
# Routes — pages
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    return render_template("index.html")


# ---------------------------------------------------------------------------
# API — catalog
# ---------------------------------------------------------------------------

@app.route("/api/catalog")
def api_catalog():
    cat = get_catalog()
    d   = engine.catalog_to_dict(cat, BASE_DIR)
    return jsonify(d)


@app.route("/api/catalog/refresh", methods=["POST"])
def api_catalog_refresh():
    global _catalog_cache
    _catalog_cache = engine.build_catalog(BASE_DIR)
    d = engine.catalog_to_dict(_catalog_cache, BASE_DIR)
    return jsonify({"refreshed": True, "meta": d["_meta"]})


@app.route("/api/catalog/summary")
def api_catalog_summary():
    cat = get_catalog()
    d   = engine.catalog_to_dict(cat, BASE_DIR)
    # Build browseable tree: application → source_collection → member
    tree: dict = {}
    app_name = d["_meta"].get("application", "Legacy Retail Co")
    tree[app_name] = {}

    for pname, prog in d["programs"].items():
        coll = prog.get("source_collection", "unknown")
        tree[app_name].setdefault(coll, {"programs": [], "fields": []})
        tree[app_name][coll]["programs"].append({
            "name": pname,
            "language": prog.get("language"),
            "platform": prog.get("platform"),
            "source_path": prog.get("source_path"),
        })

    for fname, fdefs in d["fields"].items():
        for fd in fdefs:
            coll = fd.get("source_collection", "unknown")
            tree[app_name].setdefault(coll, {"programs": [], "fields": []})
            entry = {
                "name": fname,
                "container": fd.get("container"),
                "language": fd.get("language"),
                "platform": fd.get("platform"),
                "data_type": fd.get("data_type"),
                "source_path": fd.get("source_path"),
                "line_no": fd.get("line_no"),
            }
            # avoid duplicates per collection
            existing_names = [e["name"] for e in tree[app_name][coll]["fields"]]
            if fname not in existing_names:
                tree[app_name][coll]["fields"].append(entry)

    return jsonify({
        "meta": d["_meta"],
        "ibmi_physical_files": d.get("ibmi_physical_files", []),
        "cobol_copybooks": d.get("cobol_copybooks", []),
        "programs": list(d["programs"].keys()),
        "fields": list(d["fields"].keys()),
        "tree": tree,
    })


@app.route("/api/symbols")
def api_symbols():
    """Search indexed symbols. ?q=<query>&type=field|program&lang=ibmi|cobol"""
    cat   = get_catalog()
    d     = engine.catalog_to_dict(cat, BASE_DIR)
    q     = request.args.get("q", "").upper().strip()
    ftype = request.args.get("type", "").lower()
    lang  = request.args.get("lang", "").lower()

    results = []

    if ftype in ("", "field"):
        for fname, fdefs in d["fields"].items():
            if q and q not in fname:
                continue
            for fd in fdefs:
                if lang and fd["lang"] != lang:
                    continue
                results.append({
                    "type": "field",
                    "name": fname,
                    "lang": fd["lang"],                      # raw lang key
                    "container": fd["container"],
                    "source_collection": fd.get("source_collection"),
                    "language": fd.get("language"),
                    "platform": fd.get("platform"),
                    "source_path": fd["source_path"],
                    "line_no": fd["line_no"],
                    "data_type": fd["data_type"],
                })

    if ftype in ("", "program"):
        for pname, prog in d["programs"].items():
            if q and q not in pname:
                continue
            if lang and prog["lang"] != lang:
                continue
            results.append({
                "type": "program",
                "name": pname,
                "lang": prog["lang"],                    # raw lang key
                "source_collection": prog.get("source_collection"),
                "language": prog.get("language"),
                "platform": prog.get("platform"),
                "source_path": prog["source_path"],
            })

    return jsonify({"results": results, "count": len(results)})


# ---------------------------------------------------------------------------
# API — impact analysis
# ---------------------------------------------------------------------------

@app.route("/api/analyze", methods=["POST"])
def api_analyze():
    """
    POST JSON: {
        "artifact": "ORDSTS",
        "artifact_type": "field",       // "field" | "program"
        "lang": "ibmi",                 // "ibmi" | "cobol" | null
        "change_request": "..."         // plain-text description (stored, not interpreted)
    }
    Returns structured impact report.
    """
    body = request.get_json(force=True) or {}
    artifact      = str(body.get("artifact", "")).strip().upper()
    artifact_type = str(body.get("artifact_type", "field")).strip().lower()
    lang_filter   = str(body.get("lang", "") or "").strip().lower() or None
    change_text   = str(body.get("change_request", "")).strip()

    if not artifact:
        return jsonify({"error": "artifact is required"}), 400

    # Validate artifact_type
    if artifact_type not in ("field", "program"):
        return jsonify({"error": "artifact_type must be 'field' or 'program'"}), 400

    # Validate lang_filter if supplied
    if lang_filter and lang_filter not in ("ibmi", "cobol"):
        return jsonify({"error": "lang must be 'ibmi' or 'cobol'"}), 400

    cat = get_catalog()
    rpt = engine.run_traversal(artifact, artifact_type, lang_filter, cat, BASE_DIR)

    # Serialize the report
    def ev_to_dict(ev: engine.Evidence) -> dict:
        return {
            "source_path": ev.source_path,
            "line_no": ev.line_no,
            "line_text": ev.line_text,
            "match_text": ev.match_text,
        }

    def dep_to_dict(dep: engine.Dependency) -> dict:
        return {
            "target": dep.target,
            "relationship": dep.relationship,
            "tier": dep.tier,
            "note": dep.note,
            "review_question": dep.review_question,
            "evidence": [ev_to_dict(e) for e in dep.evidence],
            # user triage state — starts unset
            "triage": None,
        }

    return jsonify({
        "starting_artifact": rpt.starting_artifact,
        "artifact_type": rpt.artifact_type,
        "lang": rpt.lang,
        "change_request": change_text,
        "engine_disclaimer": (
            "The engine performs static text search over fictional representative source files. "
            "Confirmed = source reference found at the cited path and line. "
            "Behavioral impact is NOT confirmed. "
            "This is a source-repository analysis prototype — no IBM i or mainframe connection exists."
        ),
        "confirmed": [dep_to_dict(d) for d in rpt.confirmed],
        "needs_review": [dep_to_dict(d) for d in rpt.needs_review],
        "unknown": rpt.unknown,
        "confirmed_count": len(rpt.confirmed),
        "needs_review_count": len(rpt.needs_review),
    })


# ---------------------------------------------------------------------------
# API — source viewer
# ---------------------------------------------------------------------------

@app.route("/api/source")
def api_source():
    """
    ?path=src/QDDSSRC/ORDHDR.DDS&line=10
    Returns line-numbered source content. Path must be inside src/.
    """
    rel_path   = request.args.get("path", "").strip()
    highlight  = int(request.args.get("line", 0) or 0)
    if not rel_path:
        return jsonify({"error": "path parameter required"}), 400
    result = _safe_read_source(rel_path, highlight)
    return jsonify(result)


# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    # Pre-warm the catalog
    get_catalog()
    print("Change Impact Workbench — Legacy Retail Co")
    print("Open: http://127.0.0.1:5000")
    app.run(debug=True, port=5000, use_reloader=False)
