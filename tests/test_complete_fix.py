"""
test_complete_fix.py — IBM i Complete-Fix Tests
================================================
Legacy Retail Co — Change Impact Workbench demonstration

EXECUTION ENVIRONMENT: Python / pytest.

Scenario: After the workbench identified INVUPDJOB and COMMJOB as
confirmed consumers with needs-review predicates, the developer
fixed both programs:
  INVUPDJOB.GEN_PICKLIST: WHERE ORDSTS IN ('O','P')
  COMMJOB.CalcDailyComm:  WHERE ORDSTS = 'P'

All baseline invariants are restored. Every test must pass green.
"""

import sys
from pathlib import Path
from decimal import Decimal

sys.path.insert(0, str(Path(__file__).parent.parent / "sim"))

from retailco_sim import (
    make_fixed_orders,
    invupdjob_alloc_orders,
    invupdjob_gen_picklist_fixed,
    commjob_calc_commission_fixed,
    commission_by_rep,
    pricecalc_half_up,
    pricecalc_half_even,
)

orders = make_fixed_orders()   # 1001-O, 1002-P, 1003-C, 1004-X, 1005-H


# ---------------------------------------------------------------------------
# INV-1: Hold order must not appear on pick list (fixed predicate)
# ---------------------------------------------------------------------------

def test_pick_list_excludes_hold_after_fix():
    """Fixed: WHERE ORDSTS IN ('O','P') — H excluded from pick list."""
    pick_list = invupdjob_gen_picklist_fixed(orders)
    assert 1005 not in pick_list, f"Hold order 1005 must not be on pick list; got {pick_list}"


def test_pick_list_still_includes_open_and_picking():
    """Regression: Open (O) and Picking (P) orders still on list after fix."""
    pick_list = invupdjob_gen_picklist_fixed(orders)
    assert 1001 in pick_list
    assert 1002 in pick_list


def test_pick_list_exact_set_after_fix():
    """Exact pick list after fix: {1001, 1002} — hold order absent."""
    pick_list = invupdjob_gen_picklist_fixed(orders)
    assert set(pick_list) == {1001, 1002}, f"Expected {{1001,1002}}, got {set(pick_list)}"


# ---------------------------------------------------------------------------
# INV-2: Hold order must not earn commission (fixed predicate)
# ---------------------------------------------------------------------------

def test_commission_excludes_hold_after_fix():
    """Fixed: WHERE ORDSTS = 'P' — H not eligible for commission."""
    records = commjob_calc_commission_fixed(orders)
    ordnos  = [r.ordno for r in records]
    assert 1005 not in ordnos, f"Hold order 1005 must not earn commission; records={records}"


def test_commission_rep1_correct_after_fix():
    """REP1 commission = $2.50 (order 1002 only) after fix."""
    records = commjob_calc_commission_fixed(orders)
    by_rep  = commission_by_rep(records)
    assert by_rep.get("REP1", Decimal("0")) == Decimal("2.50"), \
        f"REP1 commission expected $2.50, got {by_rep.get('REP1')}"


def test_commission_no_regression_on_picking():
    """Regression: Picking order 1002 still earns commission after fix."""
    records = commjob_calc_commission_fixed(orders)
    ordnos  = [r.ordno for r in records]
    assert 1002 in ordnos


# ---------------------------------------------------------------------------
# ALLOC_ORDERS — safe throughout (positive predicate, unaffected by CR-1)
# ---------------------------------------------------------------------------

def test_alloc_unaffected_by_hold():
    """ALLOC_ORDERS uses = 'O' — H was never included. Safe at all stages."""
    allocated = invupdjob_alloc_orders(orders)
    assert 1005 not in allocated
    assert 1001 in allocated


# ---------------------------------------------------------------------------
# PRICECALC — CR-2 rounding boundary (demonstrates second change request)
# ---------------------------------------------------------------------------

def test_pricecalc_half_up_unchanged():
    """Baseline HALF_UP rounding still works correctly for non-boundary values."""
    assert pricecalc_half_up(Decimal("25.00"), 2) == Decimal("25.00")
    assert pricecalc_half_up(Decimal("10.00"), 10) == Decimal("9.50")


def test_pricecalc_rounding_boundary_differs():
    """
    CR-2 boundary: $1.225 × 1
    HALF_UP  → $1.23  (current production behaviour)
    HALF_EVEN→ $1.22  (proposed change)
    This test proves the two modes differ — callers of PRICECALC would be affected.
    """
    half_up   = pricecalc_half_up(Decimal("1.225"), 1)
    half_even = pricecalc_half_even(Decimal("1.225"), 1)
    assert half_up   == Decimal("1.23"), f"HALF_UP expected $1.23, got {half_up}"
    assert half_even == Decimal("1.22"), f"HALF_EVEN expected $1.22, got {half_even}"
    assert half_up != half_even, "Boundary case must differ between rounding modes"
