"""
conftest.py — pytest configuration for Change Impact Workbench tests
=====================================================================
Legacy Retail Co — IBM Bob 2.0 Hackathon

Marker definitions
------------------
demo
    Marks tests that intentionally fail to demonstrate the hidden
    dependency scenario (incomplete-change, pre-fix state).
    Excluded from the default pytest run via pytest.ini addopts.
    Run explicitly with:
        python -m pytest -m demo tests/test_incomplete_change.py -v

    These are NOT xfail tests. The assertion failure IS the result
    being demonstrated: the broken predicate produces a wrong output
    row or wrong monetary total that the test measures precisely.

Classification of what each test suite exercises
-------------------------------------------------
test_baseline.py
    Python simulation — executes retailco_sim.py functions that
    implement the SQL predicate logic from representative IBM i RPG
    source. No IBM i compiler or runtime is involved.

test_incomplete_change.py  [demo marker — excluded from default run]
    Python simulation — same harness, with order 1005 (ORDSTS='H')
    added. Demonstrates that the pre-fix predicates in INVUPDJOB and
    COMMJOB produce wrong output when H is introduced.

test_complete_fix.py
    Python simulation — same harness with fixed predicates. Verifies
    INV-1 and INV-2 are restored and no regression on existing orders.

test_cobol_billing.py
    Python simulation (billing_sim.py) + engine coverage check.
    Simulation functions implement COBOL COMPUTE and MOVE logic from
    representative COBOL source. The engine coverage test calls
    ciw_engine.traverse_field() directly and asserts it finds the
    correct confirmed targets in the synthetic COBOL source files.
    No COBOL compiler or runtime is involved.
"""

import pytest


def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "demo: intentional failure scenario demonstrating hidden dependency impact"
    )
