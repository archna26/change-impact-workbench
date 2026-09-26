"""
test_incomplete_change.py — Incomplete-Change Hidden Dependency Demo
====================================================================
Legacy Retail Co — Change Impact Workbench demonstration

EXECUTION ENVIRONMENT: Python / pytest simulation harness.
These tests call retailco_sim.py functions that implement the SQL
predicate logic from representative IBM i RPG source files.
No IBM i compiler or runtime is involved.

MARKER: @pytest.mark.demo
These tests are EXCLUDED from the default pytest run.
Run them explicitly to reproduce the hidden-dependency scenario:

    python -m pytest -m demo tests/test_incomplete_change.py -v

WHY THESE TESTS FAIL (by design)
---------------------------------
Scenario: A developer updates ORDENTRY.RPGLE to accept 'H' (Hold)
as a valid order status. The batch programs INVUPDJOB and COMMJOB
are NOT yet updated. Order 1005 (ORDSTS='H') is then placed.

What is actually tested
-----------------------
Each test asserts a correct business invariant (INV-1 and INV-2)
against the PRE-FIX predicate logic. The assertion measures a real,
observable wrong output: a spurious pick-list row and an inflated
commission total. The assertion failure IS the result — it shows
precisely what breaks and by how much.

These are NOT xfail placeholders. They are executable proof of the
hidden dependencies identified by the Change Impact Workbench.

To see the green version of the same invariants, run:
    python -m pytest tests/test_complete_fix.py -v
"""

import sys
import pytest
from pathlib import Path
from decimal import Decimal

sys.path.insert(0, str(Path(__file__).parent.parent / "sim"))

from retailco_sim import (
    make_incomplete_change_orders,
    invupdjob_gen_picklist_broken,
    commjob_calc_commission_broken,
    commission_by_rep,
)

orders = make_incomplete_change_orders()   # 1001-O, 1002-P, 1003-C, 1004-X, 1005-H


@pytest.mark.demo
def test_pick_list_excludes_hold_orders():
    """
    What is tested: INV-1 — held orders must not appear on the warehouse pick list.

    Simulation source: invupdjob_gen_picklist_broken() in retailco_sim.py
    Implements predicate from: src/QRPGLESRC/INVUPDJOB.RPGLE lines 56–57
    Predicate text: WHERE h.ORDSTS <> 'C' AND h.ORDSTS <> 'X'

    Why it fails here: 'H' satisfies both <> 'C' and <> 'X', so order 1005
    is included in the pick list. The assertion measures the spurious row
    directly: hold_orders_on_list must be [] but is [1005].

    CIW engine evidence: INVUPDJOB confirmed at src/QRPGLESRC/INVUPDJOB.RPGLE:56
    with relationship SQL_PREDICATE; predicate semantics listed under needs-review.

    Fixed by: test_complete_fix.py::test_pick_list_excludes_hold_after_fix
    Fix applied: predicate changed to WHERE ORDSTS IN ('O', 'P')
    """
    pick_list = invupdjob_gen_picklist_broken(orders)
    hold_orders_on_list = [n for n in pick_list
                           if any(o.ordno == n and o.ordsts == "H" for o in orders)]
    assert hold_orders_on_list == [], \
        f"[DEMO FAIL — expected] Pick list contains held order(s): {hold_orders_on_list}. " \
        f"Full pick list: {pick_list}. " \
        f"Demonstrates INV-1 violation. Fix: change predicate to IN ('O','P')."


@pytest.mark.demo
def test_commission_excludes_hold_orders():
    """
    What is tested: INV-2 — commission must not be paid for held orders.

    Simulation source: commjob_calc_commission_broken() in retailco_sim.py
    Implements predicate from: src/QRPGLESRC/COMMJOB.RPGLE line 35
    Predicate text: WHERE h.ORDSTS NOT IN ('O', 'C', 'X')

    Why it fails here: 'H' satisfies NOT IN ('O','C','X'), so order 1005
    earns commission. REP1 baseline = $2.50 (order 1002 only). With 1005-H
    incorrectly included, REP1 total = $7.50 — inflated by $5.00.
    The assertion measures the exact monetary error.

    CIW engine evidence: COMMJOB confirmed at src/QRPGLESRC/COMMJOB.RPGLE:35
    with relationship SQL_PREDICATE; predicate semantics listed under needs-review.

    Fixed by: test_complete_fix.py::test_commission_excludes_hold_after_fix
    Fix applied: predicate changed to WHERE ORDSTS = 'P'
    """
    records = commjob_calc_commission_broken(orders)
    by_rep  = commission_by_rep(records)
    rep1    = by_rep.get("REP1", Decimal("0"))
    assert rep1 == Decimal("2.50"), \
        f"[DEMO FAIL — expected] REP1 commission = {rep1}, expected $2.50. " \
        f"Hold order 1005 inflated commission by $5.00. " \
        f"Demonstrates INV-2 violation. Fix: change predicate to ORDSTS = 'P'."
