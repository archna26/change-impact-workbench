"""
Change Impact Workbench (CIW) — ciw_engine.py
==============================================
IBM Bob 2.0 Hackathon — Legacy Retail Co demonstration

SOURCE FILES
  The repository under src/ contains fictional, representative source
  for two legacy stacks:
    IBM i  — DDS physical files, RPG ILE programs, CL programs
    COBOL  — copybooks (.cpy), COBOL programs (.cbl / .cob)
  Syntax is modelled on real IBM i / COBOL conventions but the files
  are synthetic: created for this demonstration, never compiled or run
  on any platform.

WHAT THIS ENGINE DOES
  Static text indexing and regex-based pattern search of those source
  files.  It does NOT perform compilation, data-flow analysis, or any
  form of platform execution.

CONFIRMED vs NEEDS-REVIEW vs UNKNOWN
  confirmed    The named token or structural pattern (DDS field,
               Dcl-F, ExtPgm, CALL PGM, SQL WHERE, COBOL CALL,
               COPY, field move/compare) was found at the cited path
               and line.  This is a SOURCE REFERENCE claim only — it
               does NOT imply a confirmed behavioral impact.
  needs-review A predicate, write, or call site was found whose
               effect on the proposed change must be verified against
               business rules or executable tests.
  unknown      Areas the engine cannot reach by static search
               (dynamic calls, copy members, binding dirs, etc.)

RELATIONSHIP LABELS
  DEFINES          field or program source definition
  WRITES_FIELD     field appears as assignment target
  READS_FIELD      field referenced in a non-predicate, non-write context
  SQL_PREDICATE    field appears in a SQL WHERE / AND / OR clause
  DIRECT_CALLER    program directly calls the starting program
  INDIRECT_CALLER  CL/JCL job calls a DIRECT_CALLER (one hop)
  COPY_MEMBER      COBOL program copies a copybook containing the field
  COBOL_CALL       COBOL CALL literal reference to a program

Usage
-----
  python sim/ciw_engine.py --catalog [--repo PATH]
  python sim/ciw_engine.py --artifact NAME --type field|program [--repo PATH]
  python sim/ciw_engine.py --artifact NAME --type field|program --lang ibmi|cobol [--repo PATH]

No artifact names are hard-coded. The starting artifact is supplied at runtime.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import textwrap
from collections import defaultdict
from dataclasses import dataclass, field as dc_field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
SCRIPT_DIR  = Path(__file__).parent      # sim/
REPO_ROOT   = SCRIPT_DIR.parent          # BOB_HT/
REPORTS_DIR = REPO_ROOT / "reports"
CATALOG_PATH = REPORTS_DIR / "artifact_catalog.json"

# Default source roots (relative to an arbitrary repo root supplied at runtime)
IBMI_SUBDIRS = {"dds": "QDDSSRC", "rpg": "QRPGLESRC", "cl": "QCLSRC"}
COBOL_SUBDIRS = {"cpy": "QCBLSRC", "cbl": "QCBLSRC"}


def _relpath(p: Path, root: Path) -> str:
    return p.relative_to(root).as_posix()


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class FieldDef:
    name: str
    file_name: str        # physical file / copybook this field belongs to
    source_path: str      # relative to repo root
    line_no: int
    data_type: str
    lang: str             # "ibmi" | "cobol"


@dataclass
class ProgramDef:
    name: str
    source_path: str
    source_type: str      # "RPGLE" | "CLP" | "CBL" | "COB"
    lang: str             # "ibmi" | "cobol"
    files_opened: List[str] = dc_field(default_factory=list)   # IBM i Dcl-F
    calls_programs: List[str] = dc_field(default_factory=list) # CL CALL PGM or COBOL CALL
    extpgm_refs: List[str] = dc_field(default_factory=list)    # IBM i ExtPgm
    copy_members: List[str] = dc_field(default_factory=list)   # COBOL COPY


@dataclass
class ArtifactCatalog:
    fields: Dict[str, List[FieldDef]]
    programs: Dict[str, ProgramDef]
    files: List[str]       # physical file / copybook names


@dataclass
class Evidence:
    source_path: str
    line_no: int
    line_text: str
    match_text: str


@dataclass
class Dependency:
    target: str
    relationship: str
    tier: str              # "confirmed" | "needs-review"
    evidence: List[Evidence] = dc_field(default_factory=list)
    note: str = ""
    review_question: str = ""


@dataclass
class ImpactReport:
    starting_artifact: str
    artifact_type: str
    lang: str
    confirmed: List[Dependency] = dc_field(default_factory=list)
    needs_review: List[Dependency] = dc_field(default_factory=list)
    unknown: List[str] = dc_field(default_factory=list)


# ---------------------------------------------------------------------------
# ── IBM i INDEXER ────────────────────────────────────────────────────────────
# ---------------------------------------------------------------------------

_DDS_FIELD = re.compile(
    r"^      A\s{12,}(?P<name>[A-Z][A-Z0-9_#@$]{0,9})\s+(?P<type>\S+(?:\s+\d+)?)",
    re.IGNORECASE,
)
_RPG_DCLF   = re.compile(r"Dcl-F\s+(?P<name>[A-Z][A-Z0-9_#@$]*)", re.IGNORECASE)
_RPG_EXTPGM = re.compile(r"ExtPgm\s*\(\s*['\"](?P<pgm>[A-Z][A-Z0-9_#@$]*)['\"]", re.IGNORECASE)
_CL_CALL    = re.compile(r"CALL\s+PGM\s*\(\s*(?P<pgm>[A-Z][A-Z0-9_#@$]*)\s*\)", re.IGNORECASE)

# RPG write: FIELDNAME = <something>  (field token on the LHS of assignment)
_RPG_WRITE  = re.compile(r"^\s*(?P<field>[A-Z][A-Z0-9_#@$]*)\s*=\s*\S", re.IGNORECASE)

# SQL predicate lines (WHERE / AND / OR with a comparator)
_SQL_PRED   = re.compile(
    r"(?:WHERE|AND\b|OR\b).*\b[A-Z][A-Z0-9_.]*\b\s*(?:=|<>|!=|NOT\s+IN\b|IN\b|>=|<=|>|<)",
    re.IGNORECASE,
)


def _index_dds(path: Path, root: Path) -> Tuple[str, List[FieldDef]]:
    stem   = path.stem.upper()
    fields: List[FieldDef] = []
    for lineno, raw in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
        if len(raw) > 6 and raw[6] == "*":
            continue
        m = _DDS_FIELD.match(raw.rstrip())
        if m and m.group("name").upper() not in ("R", "K"):
            fields.append(FieldDef(
                name=m.group("name").upper(),
                file_name=stem,
                source_path=_relpath(path, root),
                line_no=lineno,
                data_type=m.group("type").strip(),
                lang="ibmi",
            ))
    return stem, fields


def _index_rpgle(path: Path, root: Path) -> ProgramDef:
    pgm = ProgramDef(name=path.stem.upper(), source_path=_relpath(path, root),
                     source_type="RPGLE", lang="ibmi")
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        for m in _RPG_DCLF.finditer(line):
            f = m.group("name").upper()
            if f not in pgm.files_opened:
                pgm.files_opened.append(f)
        for m in _RPG_EXTPGM.finditer(line):
            p = m.group("pgm").upper()
            if p not in pgm.extpgm_refs:
                pgm.extpgm_refs.append(p)
    return pgm


def _index_clp(path: Path, root: Path) -> ProgramDef:
    pgm = ProgramDef(name=path.stem.upper(), source_path=_relpath(path, root),
                     source_type="CLP", lang="ibmi")
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        for m in _CL_CALL.finditer(line):
            p = m.group("pgm").upper()
            if p not in pgm.calls_programs:
                pgm.calls_programs.append(p)
    return pgm


# ---------------------------------------------------------------------------
# ── COBOL INDEXER ────────────────────────────────────────────────────────────
# ---------------------------------------------------------------------------

# COBOL data item in copybook / Working-Storage: level + name
# Matches:  05  FIELD-NAME  PIC X(10).   or   01  REC-NAME.
_COBOL_FIELD = re.compile(
    r"^\s*(?P<level>\d{2})\s+(?P<name>[A-Z][A-Z0-9-]*)\s+(?:PIC|PICTURE|REDEFINES|OCCURS|VALUE|\.|$)",
    re.IGNORECASE,
)

# COBOL CALL literal:  CALL 'PGMNAME'  or  CALL "PGMNAME"
_COBOL_CALL = re.compile(r"\bCALL\s+['\"](?P<pgm>[A-Z][A-Z0-9-]*)['\"]", re.IGNORECASE)

# COBOL COPY:  COPY COPYBOOK-NAME  (optionally followed by . or IN/OF library)
_COBOL_COPY = re.compile(r"\bCOPY\s+(?P<mbr>[A-Z][A-Z0-9-]*)(?:\s+IN\s+\S+)?", re.IGNORECASE)

# COBOL MOVE / IF / EVALUATE containing a field name — used as generic reference
_COBOL_MOVE = re.compile(r"\bMOVE\s+\S+\s+TO\s+(?P<field>[A-Z][A-Z0-9-]*)", re.IGNORECASE)


def _index_cbl(path: Path, root: Path) -> ProgramDef:
    """Index a COBOL program (.cbl / .cob) for CALL and COPY statements."""
    pgm = ProgramDef(name=path.stem.upper(), source_path=_relpath(path, root),
                     source_type=path.suffix.upper().lstrip("."), lang="cobol")
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        stripped = line.strip()
        if stripped.startswith("*"):
            continue
        for m in _COBOL_CALL.finditer(line):
            p = m.group("pgm").upper()
            if p not in pgm.calls_programs:
                pgm.calls_programs.append(p)
        for m in _COBOL_COPY.finditer(line):
            mb = m.group("mbr").upper()
            if mb not in pgm.copy_members:
                pgm.copy_members.append(mb)
    return pgm


def _index_cpy(path: Path, root: Path) -> Tuple[str, List[FieldDef]]:
    """Index a COBOL copybook (.cpy) for field definitions."""
    stem   = path.stem.upper()
    fields: List[FieldDef] = []
    for lineno, raw in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
        stripped = raw.strip()
        if stripped.startswith("*"):
            continue
        m = _COBOL_FIELD.match(stripped)
        if m:
            name = m.group("name").upper()
            # Skip group-level items (no PIC) and FILLER
            if name == "FILLER":
                continue
            fields.append(FieldDef(
                name=name,
                file_name=stem,
                source_path=_relpath(path, root),
                line_no=lineno,
                data_type=stripped[:80],
                lang="cobol",
            ))
    return stem, fields


# ---------------------------------------------------------------------------
# ── CATALOG BUILDER ──────────────────────────────────────────────────────────
# ---------------------------------------------------------------------------

def build_catalog(repo_root: Path = REPO_ROOT) -> ArtifactCatalog:
    """
    Walk src/ under repo_root and index every IBM i and COBOL source file.
    Every catalog entry is extracted from a file on disk — no synthetic data
    is inserted by the engine.
    """
    all_fields: Dict[str, List[FieldDef]] = defaultdict(list)
    programs:   Dict[str, ProgramDef]     = {}
    phys_files: List[str]                 = []

    src = repo_root / "src"

    # ── IBM i DDS ────────────────────────────────────────────────────────────
    dds_dir = src / "QDDSSRC"
    if dds_dir.exists():
        for p in sorted(dds_dir.glob("*.DDS")):
            stem, flist = _index_dds(p, repo_root)
            phys_files.append(stem)
            for fd in flist:
                all_fields[fd.name].append(fd)

    # ── IBM i RPG ILE ─────────────────────────────────────────────────────────
    rpg_dir = src / "QRPGLESRC"
    if rpg_dir.exists():
        for p in sorted(rpg_dir.glob("*.RPGLE")):
            pgm = _index_rpgle(p, repo_root)
            programs[pgm.name] = pgm

    # ── IBM i CL ─────────────────────────────────────────────────────────────
    cl_dir = src / "QCLSRC"
    if cl_dir.exists():
        for p in sorted(cl_dir.glob("*.CLP")):
            pgm = _index_clp(p, repo_root)
            programs[pgm.name] = pgm

    # ── COBOL copybooks ──────────────────────────────────────────────────────
    cbl_dir = src / "QCBLSRC"
    if cbl_dir.exists():
        for p in sorted(cbl_dir.glob("*.CPY")):
            stem, flist = _index_cpy(p, repo_root)
            phys_files.append(stem)
            for fd in flist:
                all_fields[fd.name].append(fd)
        # ── COBOL programs ───────────────────────────────────────────────────
        for ext in ("*.CBL", "*.COB"):
            for p in sorted(cbl_dir.glob(ext)):
                pgm = _index_cbl(p, repo_root)
                programs[pgm.name] = pgm

    return ArtifactCatalog(fields=dict(all_fields), programs=programs, files=phys_files)


# ---------------------------------------------------------------------------
# Domain model helpers
# ---------------------------------------------------------------------------

_SOURCE_TYPE_TO_LANGUAGE = {
    "RPGLE":  "ILE RPG",
    "CLP":    "CL",
    "CBL":    "COBOL",
    "COB":    "COBOL",
    "CPY":    "COBOL Copybook",
    "DDS":    "DDS",
}

_LANG_TO_PLATFORM = {
    "ibmi":  "IBM i",
    "cobol": "Unknown — no JCL/compiler metadata present",
}


def _source_collection(source_path: str) -> str:
    """Derive the source collection name (QDDSSRC, QRPGLESRC, etc.) from path."""
    parts = source_path.replace("\\", "/").split("/")
    # Convention: src/<COLLECTION>/<member>
    if len(parts) >= 3 and parts[0] == "src":
        return parts[1]
    if len(parts) >= 2:
        return parts[-2]
    return "unknown"


def catalog_to_dict(cat: ArtifactCatalog, repo_root: Path = REPO_ROOT) -> dict:
    # Build file→lang map from fields (cat.fields is keyed by field name, not file name)
    _file_lang: Dict[str, str] = {}
    for _defs in cat.fields.values():
        for _fd in _defs:
            _file_lang.setdefault(_fd.file_name, _fd.lang)

    # Separate IBM i DDS physical files from COBOL copybooks
    ibmi_phys      = sorted(f for f in cat.files if _file_lang.get(f) == "ibmi")
    cobol_cpybooks = sorted(f for f in cat.files if _file_lang.get(f) == "cobol")

    return {
        "_meta": {
            "generated_by": "ciw_engine.py",
            "application": "Legacy Retail Co",
            "note": (
                "Entries extracted from fictional representative source files. "
                "Files are synthetic — not compiled or run on any platform. "
                "IBM i stack: DDS physical files, ILE RPG programs, CL programs. "
                "COBOL stack: copybooks and programs (platform unknown — no JCL or "
                "compiler metadata present in this repository)."
            ),
            "ibmi_physical_files_indexed": len(ibmi_phys),
            "cobol_copybooks_indexed": len(cobol_cpybooks),
            "programs_indexed": len(cat.programs),
            "unique_field_names_indexed": len(cat.fields),
        },
        # Separated by artifact type — not merged
        "ibmi_physical_files": ibmi_phys,
        "cobol_copybooks": cobol_cpybooks,
        # Keep legacy key so existing CLI output is not broken
        "physical_files": sorted(cat.files),
        "fields": {
            fname: [
                {
                    "field_name": fd.name,
                    "container": fd.file_name,
                    "source_path": fd.source_path,
                    "source_collection": _source_collection(fd.source_path),
                    "line_no": fd.line_no,
                    "data_type": fd.data_type,
                    "lang": fd.lang,
                    "language": _SOURCE_TYPE_TO_LANGUAGE.get("DDS" if fd.lang == "ibmi" else "CPY", "Unknown"),
                    "platform": _LANG_TO_PLATFORM.get(fd.lang, "Unknown"),
                }
                for fd in defs
            ]
            for fname, defs in sorted(cat.fields.items())
        },
        "programs": {
            pname: {
                "name": pgm.name,
                "source_path": pgm.source_path,
                "source_collection": _source_collection(pgm.source_path),
                "source_type": pgm.source_type,
                "language": _SOURCE_TYPE_TO_LANGUAGE.get(pgm.source_type, pgm.source_type),
                "platform": _LANG_TO_PLATFORM.get(pgm.lang, "Unknown"),
                "lang": pgm.lang,
                "files_opened": pgm.files_opened,
                "calls_programs": pgm.calls_programs,
                "extpgm_refs": pgm.extpgm_refs,
                "copy_members": pgm.copy_members,
            }
            for pname, pgm in sorted(cat.programs.items())
        },
    }


# ---------------------------------------------------------------------------
# ── SEARCH HELPERS ───────────────────────────────────────────────────────────
# ---------------------------------------------------------------------------

def _is_comment(raw: str, lang: str) -> bool:
    s = raw.strip()
    if s.startswith("//") or s.startswith("/*") or s.startswith("*>"):
        return True
    if lang == "ibmi" and s.startswith("*"):
        return True
    if lang == "cobol" and s.startswith("*"):
        return True
    return False


def _token_lines(path: Path, token: str, lang: str, root: Path) -> List[Evidence]:
    """All non-comment lines containing `token` as a word boundary."""
    pat = re.compile(r"\b" + re.escape(token) + r"\b", re.IGNORECASE)
    evs: List[Evidence] = []
    for lineno, raw in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
        if _is_comment(raw, lang):
            continue
        if pat.search(raw):
            evs.append(Evidence(_relpath(path, root), lineno, raw.rstrip(), raw.strip()[:120]))
    return evs


def _sql_predicate_lines(path: Path, token: str, root: Path) -> List[Evidence]:
    """Lines that are SQL predicate clauses referencing `token`."""
    tok_pat  = re.compile(r"\b" + re.escape(token) + r"\b", re.IGNORECASE)
    evs: List[Evidence] = []
    for lineno, raw in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
        s = raw.strip()
        if s.startswith("*") or s.startswith("//") or s.startswith("/*"):
            continue
        if tok_pat.search(raw) and _SQL_PRED.search(raw):
            evs.append(Evidence(_relpath(path, root), lineno, raw.rstrip(), s[:120]))
    return evs


def _write_lines(path: Path, token: str, pred_linenos: set, root: Path) -> List[Evidence]:
    """RPG assignment lines: TOKEN = <expr>  (token on LHS)."""
    tok_pat = re.compile(r"\b" + re.escape(token) + r"\b", re.IGNORECASE)
    evs: List[Evidence] = []
    for lineno, raw in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
        if lineno in pred_linenos:
            continue
        s = raw.strip()
        if s.startswith("*") or s.startswith("//"):
            continue
        if not tok_pat.search(raw):
            continue
        m = _RPG_WRITE.match(s)
        if m and m.group("field").upper() == token.upper():
            evs.append(Evidence(_relpath(path, root), lineno, raw.rstrip(), s[:120]))
    return evs


def _cobol_move_lines(path: Path, token: str, root: Path) -> List[Evidence]:
    """COBOL MOVE ... TO TOKEN  (token on the receiving end = write)."""
    evs: List[Evidence] = []
    for lineno, raw in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
        s = raw.strip()
        if s.startswith("*"):
            continue
        m = _COBOL_MOVE.search(raw)
        if m and m.group("field").upper() == token.upper():
            evs.append(Evidence(_relpath(path, root), lineno, raw.rstrip(), s[:120]))
    return evs


# ---------------------------------------------------------------------------
# ── TRAVERSAL — FIELD ────────────────────────────────────────────────────────
# ---------------------------------------------------------------------------

def traverse_field(artifact: str, cat: ArtifactCatalog,
                   lang_filter: Optional[str], repo_root: Path) -> ImpactReport:
    token = artifact.upper()
    rpt   = ImpactReport(starting_artifact=token, artifact_type="field",
                         lang=lang_filter or "any")

    # Step 1: definition(s)
    defs = [d for d in cat.fields.get(token, [])
            if lang_filter is None or d.lang == lang_filter]
    if not defs:
        rpt.unknown.append(
            f"Field '{token}' not found in any indexed "
            f"{'DDS' if lang_filter == 'ibmi' else 'copybook' if lang_filter == 'cobol' else 'DDS/copybook'} "
            "file. Verify name and re-run --catalog.")
        return rpt

    for fd in defs:
        rpt.confirmed.append(Dependency(
            target=f"{fd.file_name}.{fd.name}",
            relationship="DEFINES",
            tier="confirmed",
            evidence=[Evidence(fd.source_path, fd.line_no, fd.data_type, fd.data_type)],
            note=f"Field defined in fictional representative {'DDS' if fd.lang == 'ibmi' else 'COBOL copybook'} for {fd.file_name}.",
        ))

    host_containers = {fd.file_name for fd in defs}
    host_lang       = {fd.lang for fd in defs}
    directly_affected: List[str] = []

    # Step 2+3: programs that access host containers
    for pname, pgm in sorted(cat.programs.items()):
        if lang_filter and pgm.lang != lang_filter:
            continue

        pgm_path    = repo_root / pgm.source_path
        opens_host  = False

        if pgm.lang == "ibmi":
            opens_host = bool(set(pgm.files_opened) & host_containers)
        elif pgm.lang == "cobol":
            opens_host = bool(set(pgm.copy_members) & host_containers)

        pred_evs  = _sql_predicate_lines(pgm_path, token, repo_root) if pgm.lang == "ibmi" else []
        pred_nos  = {e.line_no for e in pred_evs}
        write_evs = (
            _write_lines(pgm_path, token, pred_nos, repo_root) if pgm.lang == "ibmi"
            else _cobol_move_lines(pgm_path, token, repo_root)
        )
        all_tok   = _token_lines(pgm_path, token, pgm.lang, repo_root)
        read_evs  = [e for e in all_tok if e.line_no not in pred_nos
                     and e.line_no not in {w.line_no for w in write_evs}]

        has_any = pred_evs or write_evs or read_evs
        if not has_any:
            continue

        tier = "confirmed" if opens_host else "needs-review"
        if opens_host:
            directly_affected.append(pname)

        if pred_evs:
            rpt.confirmed.append(Dependency(
                target=pname, relationship="SQL_PREDICATE", tier="confirmed",
                evidence=pred_evs,
                note=f"SQL predicate referencing {token} found in {pgm.source_path}. Reference confirmed.",
            ))
            rpt.needs_review.append(Dependency(
                target=f"{pname} — predicate semantics",
                relationship="SQL_PREDICATE", tier="needs-review",
                evidence=pred_evs,
                note="Predicate text extracted. Determine whether it handles the new value correctly.",
                review_question=(
                    f"Is the predicate in {pname} exhaustive-positive, exhaustive-negative, "
                    f"or already correct for '{token}' = <new-value>?"
                ),
            ))

        if write_evs:
            rpt.confirmed.append(Dependency(
                target=pname, relationship="WRITES_FIELD", tier="confirmed",
                evidence=write_evs,
                note=f"Assignment to {token} found in {pgm.source_path}. Confirm new value is written and validated.",
            ))

        if read_evs and not pred_evs and not write_evs:
            rpt.confirmed.append(Dependency(
                target=pname, relationship="READS_FIELD", tier="confirmed",
                evidence=read_evs,
                note=f"Field referenced in {pgm.source_path}. Verify usage is compatible with new value.",
            ))

        if pgm.lang == "cobol" and opens_host:
            # COBOL COPY reference
            rpt.confirmed.append(Dependency(
                target=pname, relationship="COPY_MEMBER", tier="confirmed",
                evidence=[Evidence(pgm.source_path, 1, f"COPY {list(host_containers & set(pgm.copy_members))[0]}", "COPY")],
                note=f"{pname} COPYs {host_containers & set(pgm.copy_members)} — field is in scope.",
            ))

        if not opens_host and has_any:
            all_evs = pred_evs or write_evs or read_evs
            rpt.needs_review.append(Dependency(
                target=pname, relationship="READS_FIELD", tier="needs-review",
                evidence=list(all_evs),
                note=f"Token '{token}' found but {pname} does not declare the host container. May be indirect.",
                review_question=f"Confirm whether {pname} accesses {token} directly or via an intermediate.",
            ))

    # Step 4: indirect callers (CL/COBOL jobs calling directly-affected)
    for pname, pgm in sorted(cat.programs.items()):
        if lang_filter and pgm.lang != lang_filter:
            continue
        if pname in directly_affected:
            continue
        all_calls = pgm.calls_programs + pgm.extpgm_refs
        for called in all_calls:
            if called in directly_affected:
                pgm_path = repo_root / pgm.source_path
                evs = _token_lines(pgm_path, called, pgm.lang, repo_root)
                rpt.confirmed.append(Dependency(
                    target=pname, relationship="INDIRECT_CALLER", tier="confirmed",
                    evidence=evs,
                    note=f"Calls {called}, which has a confirmed reference to {token}. Verify downstream output.",
                ))
                break

    # Known unknowns
    rpt.unknown += [
        "Dynamic calls (variable program name) cannot be resolved by static search.",
        "COBOL ALTER / GO TO and computed CALL cannot be resolved.",
        "IBM i copy members (/COPY, /INCLUDE) and binding directory entries are not indexed.",
        "RPG fields accessed via locally-renamed variables may be missed.",
        "Predicate behavioral meaning (safe vs broken) is listed under 'needs-review' — "
        "confirm with business rules and executable tests.",
    ]
    return rpt


# ---------------------------------------------------------------------------
# ── TRAVERSAL — PROGRAM ──────────────────────────────────────────────────────
# ---------------------------------------------------------------------------

def traverse_program(artifact: str, cat: ArtifactCatalog,
                     lang_filter: Optional[str], repo_root: Path) -> ImpactReport:
    token = artifact.upper()
    rpt   = ImpactReport(starting_artifact=token, artifact_type="program",
                         lang=lang_filter or "any")

    if token not in cat.programs:
        rpt.unknown.append(f"Program '{token}' not found in catalog. Verify name and re-run --catalog.")
        return rpt

    pgm_def = cat.programs[token]
    rpt.confirmed.append(Dependency(
        target=token, relationship="DEFINES", tier="confirmed",
        evidence=[Evidence(pgm_def.source_path, 1,
                           f"Program {token} ({pgm_def.source_type})",
                           f"defined in {pgm_def.source_path}")],
        note="Program definition in fictional representative source. Root node.",
    ))

    direct_callers: List[str] = []

    for pname, pgm in sorted(cat.programs.items()):
        if pname == token:
            continue
        if lang_filter and pgm.lang != lang_filter:
            continue

        extpgm_hit  = token in pgm.extpgm_refs
        cl_call_hit = token in pgm.calls_programs    # covers both CL and COBOL CALL
        pgm_path    = repo_root / pgm.source_path
        token_evs   = _token_lines(pgm_path, token, pgm.lang, repo_root)

        if not (extpgm_hit or cl_call_hit or token_evs):
            continue

        if extpgm_hit:
            tier = "confirmed"
            rel  = "DIRECT_CALLER"
            note = f"ExtPgm('{token}') prototype found — confirmed direct caller."
            evs  = token_evs
        elif cl_call_hit:
            tier = "confirmed"
            rel  = "COBOL_CALL" if pgm.lang == "cobol" else "DIRECT_CALLER"
            note = f"CALL {'literal' if pgm.lang == 'cobol' else 'PGM'}({token}) found — confirmed direct caller."
            evs  = token_evs
        else:
            tier = "needs-review"
            rel  = "DIRECT_CALLER"
            note = f"Token '{token}' found without structural call indicator — possible reference or comment."
            evs  = token_evs

        dep = Dependency(target=pname, relationship=rel, tier=tier, evidence=evs, note=note,
                         review_question="" if tier == "confirmed" else
                         f"Confirm {pname} actually calls {token} at this site.")
        if tier == "confirmed":
            rpt.confirmed.append(dep)
            direct_callers.append(pname)
        else:
            rpt.needs_review.append(dep)

    # Indirect callers: jobs/programs that call a direct caller
    for pname, pgm in sorted(cat.programs.items()):
        if lang_filter and pgm.lang != lang_filter:
            continue
        if pname in direct_callers or pname == token:
            continue
        all_calls = pgm.calls_programs
        for called in all_calls:
            if called in direct_callers:
                pgm_path = repo_root / pgm.source_path
                evs = _token_lines(pgm_path, called, pgm.lang, repo_root)
                rpt.confirmed.append(Dependency(
                    target=pname, relationship="INDIRECT_CALLER", tier="confirmed",
                    evidence=evs,
                    note=f"Calls {called}, which directly calls {token}. One-hop indirect dependency.",
                ))
                break

    rpt.unknown += [
        "Dynamic CALL / computed GOTO cannot be resolved by static search.",
        "IBM i copy members and binding directory entries are not indexed.",
        "COBOL PERFORM THROUGH ranges are not traced.",
        "Behavioral impact on each caller requires human review and executable tests.",
    ]
    return rpt


def run_traversal(artifact: str, artifact_type: str,
                  lang_filter: Optional[str], cat: ArtifactCatalog,
                  repo_root: Path) -> ImpactReport:
    t = artifact_type.lower()
    if t == "field":
        return traverse_field(artifact, cat, lang_filter, repo_root)
    elif t in ("program", "pgm"):
        return traverse_program(artifact, cat, lang_filter, repo_root)
    else:
        rpt = ImpactReport(artifact, artifact_type, lang_filter or "any")
        rpt.unknown.append(f"Artifact type '{artifact_type}' not supported. Use: field, program.")
        return rpt


# ---------------------------------------------------------------------------
# ── REPORT BUILDERS ──────────────────────────────────────────────────────────
# ---------------------------------------------------------------------------

def _fmt_ev(evs: List[Evidence]) -> str:
    if not evs:
        return "  - (no direct evidence line)"
    return "\n".join(f"  - `{e.source_path}:{e.line_no}` → `{e.match_text}`" for e in evs)


def build_impact_report_md(rpt: ImpactReport) -> str:
    lines = [
        "# Change Impact Report",
        "",
        "> **Source files:** Fictional representative source files (IBM i DDS/RPG ILE/CL;",
        "> COBOL copybooks and programs). Catalog evidence is genuinely extracted from",
        "> those files, but the files are synthetic — never compiled or run on any platform.",
        ">",
        "> **Confirmed** = token or structural pattern found at the cited path and line.",
        "> This is a *source reference* claim. Behavioral impact is NOT claimed.",
        ">",
        "> **Needs Review** = predicate, write, or call site found whose behavioral",
        "> effect on the proposed change must be verified by human review or tests.",
        ">",
        "> **Unknown** = areas static search cannot reach.",
        "",
        f"**Starting artifact:** `{rpt.starting_artifact}`  "
        f"| Type: `{rpt.artifact_type}`  | Language scope: `{rpt.lang}`",
        "",
        "---",
        "",
        f"## Confirmed Source References  ({len(rpt.confirmed)} found)",
        "",
    ]
    for dep in rpt.confirmed:
        lines += [
            f"### {dep.target}  `[{dep.relationship}]`",
            f"- **Note:** {dep.note}",
            "- **Evidence:**",
            _fmt_ev(dep.evidence),
            "",
        ]

    lines += [
        f"## Needs Review — Behavioral Impact Not Yet Determined  ({len(rpt.needs_review)} items)",
        "",
    ]
    if rpt.needs_review:
        for dep in rpt.needs_review:
            lines += [
                f"### {dep.target}  `[{dep.relationship}]`",
                f"- **Note:** {dep.note}",
            ]
            if dep.review_question:
                lines.append(f"- **Review question:** {dep.review_question}")
            lines += ["- **Evidence:**", _fmt_ev(dep.evidence), ""]
    else:
        lines.append("*(none)*\n")

    lines += ["## Unknown / Out-of-Scope Areas", ""]
    for u in rpt.unknown:
        lines.append(f"- {u}")
    lines.append("")
    return "\n".join(lines)


_CHECKLIST_ACTIONS = {
    "DEFINES":          "Update definition and document business rule for new value",
    "WRITES_FIELD":     "Confirm new value is written and validated correctly",
    "READS_FIELD":      "Verify read usage handles new value without error",
    "SQL_PREDICATE":    "Review predicate — determine if exhaustive/negative pattern breaks with new value",
    "DIRECT_CALLER":    "Test caller output with changed behavior; update expected values in tests",
    "COBOL_CALL":       "Test COBOL caller output with changed behavior; update expected values",
    "INDIRECT_CALLER":  "Verify end-to-end downstream output; re-run integration test",
    "COPY_MEMBER":      "Verify all COPY usages handle field change; regression test each program",
}


def build_checklist_md(rpt: ImpactReport) -> str:
    lines = [
        "# Change Checklist",
        "",
        f"**Artifact:** `{rpt.starting_artifact}` | **Type:** {rpt.artifact_type} | **Lang:** {rpt.lang}",
        "",
        "| # | Artifact | Relationship | Action Required | Tier | Owner |",
        "|---|----------|--------------|-----------------|------|-------|",
    ]
    for i, dep in enumerate(rpt.confirmed, 1):
        action = _CHECKLIST_ACTIONS.get(dep.relationship, "Review for compatibility")
        lines.append(f"| {i} | `{dep.target}` | {dep.relationship} | {action} | confirmed | Developer |")
    for i, dep in enumerate(rpt.needs_review, len(rpt.confirmed) + 1):
        action = dep.review_question or "Confirm or dismiss — human review required"
        lines.append(f"| {i} | `{dep.target}` | {dep.relationship} | {action} | needs-review | Developer |")
    lines.append("")
    return "\n".join(lines)


def build_regression_plan_md(rpt: ImpactReport) -> str:
    lines = [
        "# Regression Plan",
        "",
        f"**Artifact:** `{rpt.starting_artifact}` | **Type:** {rpt.artifact_type} | **Lang:** {rpt.lang}",
        "",
        "> Tests run in the Python simulation harness (sim/retailco_sim.py for IBM i (Legacy Retail Co),",
        "> sim/billing_sim.py for COBOL). These simulate the predicate and business-rule",
        "> logic from the representative source. No IBM i or COBOL platform is involved.",
        "",
        "## Test Cases",
        "",
        "| # | Test Name | Consumer | Condition | Expected Result | Pass Criteria |",
        "|---|-----------|----------|-----------|-----------------|---------------|",
    ]
    i = 1
    for dep in rpt.confirmed:
        slug = dep.target.lower().replace(".", "_").replace(" ", "_").replace("-", "_")
        if dep.relationship == "SQL_PREDICATE":
            lines.append(f"| {i} | test_{slug}_predicate_normal | {dep.target} | New value in dataset | Predicate handles new value | Assert row in/out as expected |"); i += 1
            lines.append(f"| {i} | test_{slug}_predicate_boundary | {dep.target} | Only new value present | No spurious rows | Assert exact row count |"); i += 1
        elif dep.relationship == "WRITES_FIELD":
            lines.append(f"| {i} | test_{slug}_write | {dep.target} | New value written | Value persisted | Assert stored value == new value |"); i += 1
        elif dep.relationship in ("DIRECT_CALLER", "COBOL_CALL", "INDIRECT_CALLER"):
            lines.append(f"| {i} | test_{slug}_chain | {dep.target} | End-to-end changed behavior | Output matches updated spec | Assert totals and row counts |"); i += 1
        elif dep.relationship == "COPY_MEMBER":
            lines.append(f"| {i} | test_{slug}_copy | {dep.target} | Field changed in copybook | All COPY users handle new definition | Assert each consumer produces correct output |"); i += 1
    lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# ── CLI ──────────────────────────────────────────────────────────────────────
# ---------------------------------------------------------------------------

def _resolve_repo(args) -> Path:
    if hasattr(args, "repo") and args.repo:
        return Path(args.repo).resolve()
    return REPO_ROOT


def cmd_catalog(args):
    repo = _resolve_repo(args)
    print("=== Change Impact Workbench — Catalog Mode ===")
    print(f"Repository root : {repo}")
    print("NOTE: Indexing fictional representative source files.")
    print("      Evidence is extracted from those files, but they are")
    print("      synthetic — not compiled or run on any platform.")
    print()
    cat = build_catalog(repo)
    (repo / "reports").mkdir(exist_ok=True)
    out_path = repo / "reports" / "artifact_catalog.json"
    out_path.write_text(json.dumps(catalog_to_dict(cat, repo), indent=2), encoding="utf-8")
    print(f"Physical files / copybooks indexed : {len(cat.files)}")
    print(f"Programs indexed                   : {len(cat.programs)}")
    print(f"Unique field names                 : {len(cat.fields)}")
    print(f"\nCatalog written to: {out_path}")
    return cat


def cmd_impact(args, cat: Optional[ArtifactCatalog] = None):
    repo      = _resolve_repo(args)
    artifact  = args.artifact.upper()
    atype     = args.type.lower()
    lang_filt = args.lang.lower() if hasattr(args, "lang") and args.lang else None

    print("=== Change Impact Workbench — Impact Analysis ===")
    print(f"Starting artifact : {artifact}")
    print(f"Artifact type     : {atype}")
    print(f"Language scope    : {lang_filt or 'all'}")
    print()

    if cat is None:
        cat = build_catalog(repo)

    rpt = run_traversal(artifact, atype, lang_filt, cat, repo)

    out_dir = repo / "reports"
    out_dir.mkdir(exist_ok=True)
    (out_dir / "impact_report.md").write_text(build_impact_report_md(rpt), encoding="utf-8")
    (out_dir / "change_checklist.md").write_text(build_checklist_md(rpt), encoding="utf-8")
    (out_dir / "regression_plan.md").write_text(build_regression_plan_md(rpt), encoding="utf-8")

    print(f"Confirmed source references : {len(rpt.confirmed)}")
    for d in rpt.confirmed:
        loc = f"{d.evidence[0].source_path}:{d.evidence[0].line_no}" if d.evidence else "—"
        print(f"  [CONFIRMED]  {d.target:40s}  {d.relationship:18s}  @ {loc}")

    print(f"\nNeeds review (behavioral impact not yet determined) : {len(rpt.needs_review)}")
    for d in rpt.needs_review:
        loc = f"{d.evidence[0].source_path}:{d.evidence[0].line_no}" if d.evidence else "—"
        print(f"  [REVIEW]     {d.target:40s}  {d.relationship:18s}  @ {loc}")

    print(f"\nUnknown areas : {len(rpt.unknown)}")
    for u in rpt.unknown:
        print(f"  [UNKNOWN]    {u}")

    print(f"\nReports written to: {out_dir}/")
    return rpt


def main():
    p = argparse.ArgumentParser(
        description="Change Impact Workbench — multi-language legacy source analysis",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""\
            Examples:
              python sim/ciw_engine.py --catalog
              python sim/ciw_engine.py --artifact ORDSTS --type field --lang ibmi
              python sim/ciw_engine.py --artifact PRICECALC --type program --lang ibmi
              python sim/ciw_engine.py --artifact BILL-RATE --type field --lang cobol
              python sim/ciw_engine.py --artifact CALCBILL --type program --lang cobol
        """),
    )
    p.add_argument("--catalog",  action="store_true", help="Index repository and write artifact_catalog.json")
    p.add_argument("--artifact", metavar="NAME",      help="Starting artifact name")
    p.add_argument("--type",     metavar="TYPE",      default="field", help="field | program")
    p.add_argument("--lang",     metavar="LANG",      default=None,    help="ibmi | cobol  (default: all)")
    p.add_argument("--repo",     metavar="PATH",      default=None,    help="Repository root (default: BOB_HT/)")
    args = p.parse_args()

    if not args.catalog and not args.artifact:
        p.print_help(); sys.exit(0)

    cat = cmd_catalog(args) if args.catalog else None
    if args.artifact:
        cmd_impact(args, cat)


if __name__ == "__main__":
    main()
