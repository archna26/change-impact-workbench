"""
test_web_api.py — UI / data-model tests for the Change Impact Workbench Flask app.

Classification
--------------
These are unit and integration tests of the Flask API layer and domain-model
corrections. They do NOT test IBM i or mainframe runtime behavior.
All assertions are against the fictional representative source in BOB_HT/src/.

Run:
    python -m pytest tests/test_web_api.py -v
"""

import json
import sys
from pathlib import Path

import pytest

# Ensure sim/ is importable
sys.path.insert(0, str(Path(__file__).parent.parent / "sim"))

# Import the Flask app
sys.path.insert(0, str(Path(__file__).parent.parent))
import app as ciw_app
import ciw_engine as engine


@pytest.fixture(scope="module")
def client():
    ciw_app.app.config["TESTING"] = True
    # Reset catalog cache so test session starts fresh
    ciw_app._catalog_cache = None
    with ciw_app.app.test_client() as c:
        yield c


# ---------------------------------------------------------------------------
# Domain model — catalog structure
# ---------------------------------------------------------------------------

class TestCatalogDomainModel:
    """Verify the catalog output separates artifact types and provides correct labels."""

    def test_catalog_has_separated_file_types(self, client):
        """IBM i physical files and COBOL copybooks must be in separate keys."""
        resp = client.get("/api/catalog")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "ibmi_physical_files" in data, "ibmi_physical_files key missing"
        assert "cobol_copybooks" in data, "cobol_copybooks key missing"

    def test_ibmi_physical_files_are_dds_only(self, client):
        """ibmi_physical_files must not include COBOL copybooks."""
        data = client.get("/api/catalog").get_json()
        ibmi = set(data["ibmi_physical_files"])
        # BILREC is a COBOL copybook — must NOT appear here
        assert "BILREC" not in ibmi, "BILREC (COBOL copybook) found in ibmi_physical_files"
        # ORDHDR is a DDS physical file — must appear here
        assert "ORDHDR" in ibmi, "ORDHDR not in ibmi_physical_files"

    def test_cobol_copybooks_separate(self, client):
        """cobol_copybooks must contain BILREC and not DDS files."""
        data = client.get("/api/catalog").get_json()
        cpybooks = set(data["cobol_copybooks"])
        assert "BILREC" in cpybooks, "BILREC not in cobol_copybooks"
        assert "ORDHDR" not in cpybooks, "ORDHDR (DDS file) found in cobol_copybooks"

    def test_programs_have_language_field(self, client):
        """Every program must have a 'language' field (not just 'lang')."""
        data = client.get("/api/catalog").get_json()
        for pname, prog in data["programs"].items():
            assert "language" in prog, f"{pname} missing 'language' field"
            assert prog["language"], f"{pname} has empty 'language'"

    def test_programs_have_platform_field(self, client):
        """Every program must have a 'platform' field."""
        data = client.get("/api/catalog").get_json()
        for pname, prog in data["programs"].items():
            assert "platform" in prog, f"{pname} missing 'platform'"

    def test_cobol_programs_platform_not_mainframe(self, client):
        """COBOL programs must not be labelled 'mainframe' (no JCL evidence)."""
        data = client.get("/api/catalog").get_json()
        for pname, prog in data["programs"].items():
            if prog["lang"] == "cobol":
                assert "mainframe" not in prog["platform"].lower(), (
                    f"{pname} platform incorrectly labelled as mainframe"
                )
                assert "unknown" in prog["platform"].lower(), (
                    f"{pname} COBOL platform should be 'unknown' without JCL metadata"
                )

    def test_ibmi_programs_platform_correct(self, client):
        """IBM i programs must have platform 'IBM i'."""
        data = client.get("/api/catalog").get_json()
        for pname, prog in data["programs"].items():
            if prog["lang"] == "ibmi":
                assert prog["platform"] == "IBM i", (
                    f"{pname} IBM i platform label wrong: {prog['platform']}"
                )

    def test_programs_have_source_collection(self, client):
        """Every program must have a source_collection field."""
        data = client.get("/api/catalog").get_json()
        for pname, prog in data["programs"].items():
            assert "source_collection" in prog, f"{pname} missing source_collection"
            assert prog["source_collection"] != "unknown", (
                f"{pname} source_collection resolved as 'unknown'"
            )

    def test_rpgle_language_label(self, client):
        """RPGLE programs must use language 'ILE RPG', not just 'RPGLE'."""
        data = client.get("/api/catalog").get_json()
        rpg_progs = [p for p in data["programs"].values() if p["source_type"] == "RPGLE"]
        assert rpg_progs, "No RPGLE programs found in catalog"
        for p in rpg_progs:
            assert p["language"] == "ILE RPG", (
                f"{p['name']} language should be 'ILE RPG', got {p['language']}"
            )

    def test_cl_language_label(self, client):
        """CLP programs must use language 'CL'."""
        data = client.get("/api/catalog").get_json()
        cl_progs = [p for p in data["programs"].values() if p["source_type"] == "CLP"]
        assert cl_progs, "No CLP programs found"
        for p in cl_progs:
            assert p["language"] == "CL", f"{p['name']} language should be 'CL'"

    def test_meta_has_application_name(self, client):
        """_meta must identify the application as 'Legacy Retail Co'."""
        data = client.get("/api/catalog").get_json()
        assert data["_meta"]["application"] == "Legacy Retail Co"


# ---------------------------------------------------------------------------
# API endpoints
# ---------------------------------------------------------------------------

class TestCatalogSummaryAPI:

    def test_summary_tree_contains_app(self, client):
        resp = client.get("/api/catalog/summary")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "Legacy Retail Co" in data["tree"], "Application node missing from tree"

    def test_summary_collections_present(self, client):
        data = client.get("/api/catalog/summary").get_json()
        app_tree = data["tree"]["Legacy Retail Co"]
        expected = {"QDDSSRC", "QRPGLESRC", "QCLSRC", "QCBLSRC"}
        found = set(app_tree.keys())
        missing = expected - found
        assert not missing, f"Source collections missing from tree: {missing}"

    def test_summary_counts_correct(self, client):
        data = client.get("/api/catalog/summary").get_json()
        meta = data["meta"]
        assert meta["programs_indexed"] == 9
        assert meta["ibmi_physical_files_indexed"] == 4
        assert meta["cobol_copybooks_indexed"] == 1


class TestSymbolSearchAPI:

    def test_search_ordsts(self, client):
        resp = client.get("/api/symbols?q=ORDSTS&type=field")
        data = resp.get_json()
        assert data["count"] >= 1
        names = [r["name"] for r in data["results"]]
        assert "ORDSTS" in names

    def test_search_bill_rate(self, client):
        resp = client.get("/api/symbols?q=BILL-RATE&type=field")
        data = resp.get_json()
        names = [r["name"] for r in data["results"]]
        assert "BILL-RATE" in names

    def test_search_lang_filter(self, client):
        resp = client.get("/api/symbols?lang=ibmi")
        data = resp.get_json()
        assert data["count"] > 0, "No IBM i symbols returned"
        for r in data["results"]:
            assert r.get("lang") == "ibmi", (
                f"Symbol {r.get('name')} returned with lang={r.get('lang')} "
                f"when lang=ibmi filter was applied"
            )

    def test_symbol_has_source_collection(self, client):
        """All symbol results must include source_collection."""
        resp = client.get("/api/symbols?q=ORDSTS")
        data = resp.get_json()
        for r in data["results"]:
            assert "source_collection" in r, f"source_collection missing from {r['name']}"


class TestAnalyzeAPI:

    def test_ordsts_analysis_returns_confirmed(self, client):
        resp = client.post("/api/analyze", json={
            "artifact": "ORDSTS", "artifact_type": "field",
            "lang": "ibmi", "change_request": "Add status H (Hold)",
        })
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["confirmed_count"] >= 7, (
            f"Expected >=7 confirmed, got {data['confirmed_count']}"
        )

    def test_ordsts_analysis_disclaimer_present(self, client):
        resp = client.post("/api/analyze", json={
            "artifact": "ORDSTS", "artifact_type": "field", "lang": "ibmi"
        })
        data = resp.get_json()
        assert "engine_disclaimer" in data
        # Must not claim behavioral confirmation
        assert "Behavioral impact is NOT confirmed" in data["engine_disclaimer"]

    def test_billrate_analysis(self, client):
        resp = client.post("/api/analyze", json={
            "artifact": "BILL-RATE", "artifact_type": "field",
            "lang": "cobol", "change_request": "Change precision",
        })
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["confirmed_count"] >= 5

    def test_analyze_invalid_lang(self, client):
        resp = client.post("/api/analyze", json={
            "artifact": "ORDSTS", "artifact_type": "field", "lang": "mainframe"
        })
        assert resp.status_code == 400

    def test_analyze_missing_artifact(self, client):
        resp = client.post("/api/analyze", json={"artifact_type": "field"})
        assert resp.status_code == 400

    def test_change_request_stored_in_response(self, client):
        cr = "Test change request text"
        resp = client.post("/api/analyze", json={
            "artifact": "ORDSTS", "artifact_type": "field",
            "change_request": cr,
        })
        data = resp.get_json()
        assert data["change_request"] == cr


class TestSourceViewerAPI:

    def test_valid_source_path(self, client):
        resp = client.get("/api/source?path=src/QDDSSRC/ORDHDR.DDS&line=10")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "lines" in data
        assert len(data["lines"]) > 0
        assert data["highlight_line"] == 10

    def test_path_traversal_rejected(self, client):
        resp = client.get("/api/source?path=../sim/ciw_engine.py")
        assert resp.status_code in (403, 404)

    def test_outside_src_rejected(self, client):
        resp = client.get("/api/source?path=tests/test_baseline.py")
        assert resp.status_code in (403, 404)

    def test_missing_path_param(self, client):
        resp = client.get("/api/source")
        assert resp.status_code == 400


class TestIndexPage:

    def test_index_loads(self, client):
        resp = client.get("/")
        assert resp.status_code == 200
        assert b"Change Impact Workbench" in resp.data
