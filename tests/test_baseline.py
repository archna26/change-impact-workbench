"""
test_baseline.py — IBM i Baseline Tests (pre-change, no H status)
==================================================================
Legacy Retail Co — Change Impact Workbench demonstration

EXECUTION ENVIRONMENT: Python / pytest.
These tests run against sim/retailco_sim.py, which simulates the
SQL predicate logic from representative IBM i RPG source files.
IBM i native execution is NOT involved.

Baseline: four orders (O, P, C, X). No 'H' status exists yet.
All predicates behave correctly. Every test must pass green before
any change is made to the source.
"""

import sys
from pathlib import Path
from decimal import Decimal

sys.path.insert(0, str(Path(__file__).parent.parent / "sim"))

from retailco_sim import (
    make_baseline_orders,
    invupdjob_alloc_orders,
    invupdjob_gen_picklist_broken,   # "broken" name is pre-fix; at baseline it is correct
    commjob_calc_commission_broken,  # same — at baseline this predicate is correct
    commission_by_rep,
    pricecalc_half_up,
)


orders = make_baseline_orders()   # 1001-O, 1002-P, 1003-C, 1004-X


# ---------------------------------------------------------------------------
# INVUPDJOB — ALLOC_ORDERS
# ---------------------------------------------------------------------------

def test_alloc_orders_selects_open_only():
    """Only Open orders (O) are allocated. Source: INVUPDJOB.RPGLE line 30."""
    allocated = invupdjob_alloc_orders(orders)
    assert allocated == [1001], f"Expected [1001], got {allocated}"


def test_alloc_orders_excludes_picking():
    """Picking orders (P) already allocated — must not be re-allocated."""
    allocated = invupdjob_alloc_orders(orders)
    assert 1002 not in allocated


def test_alloc_orders_excludes_closed_and_cancelled():
    """Closed (C) and Cancelled (X) orders must never be allocated."""
    allocated = invupdjob_alloc_orders(orders)
    assert 1003 not in allocated
    assert 1004 not in allocated


# ---------------------------------------------------------------------------
# INVUPDJOB — GEN_PICKLIST  (pre-fix predicate, correct at baseline)
# ---------------------------------------------------------------------------

def test_picklist_includes_open_and_picking():
    """Pick list must include Open and Picking orders. Source: INVUPDJOB.RPGLE lines 56-57."""
    pick_list = invupdjob_gen_picklist_broken(orders)
    assert 1001 in pick_list, "Open order 1001 must be on pick list"
    assert 1002 in pick_list, "Picking order 1002 must be on pick list"


def test_picklist_excludes_closed():
    """Closed orders must not be on pick list."""
    pick_list = invupdjob_gen_picklist_broken(orders)
    assert 1003 not in pick_list


def test_picklist_excludes_cancelled():
    """Cancelled orders must not be on pick list."""
    pick_list = invupdjob_gen_picklist_broken(orders)
    assert 1004 not in pick_list


def test_picklist_exact_set_baseline():
    """Exact pick list at baseline is {1001, 1002}."""
    pick_list = invupdjob_gen_picklist_broken(orders)
    assert set(pick_list) == {1001, 1002}, f"Expected {{1001,1002}}, got {set(pick_list)}"


# ---------------------------------------------------------------------------
# COMMJOB — CalcDailyComm  (pre-fix predicate, correct at baseline)
# ---------------------------------------------------------------------------

def test_commission_paid_only_for_picking():
    """Commission paid only for Picking orders. Source: COMMJOB.RPGLE lines 35-37."""
    records = commjob_calc_commission_broken(orders)
    ordnos = [r.ordno for r in records]
    assert 1002 in ordnos, "Picking order 1002 must earn commission"
    assert 1001 not in ordnos, "Open order 1001 must not earn commission"
    assert 1003 not in ordnos, "Closed order 1003 must not earn commission"
    assert 1004 not in ordnos, "Cancelled order 1004 must not earn commission"


def test_commission_amount_correct():
    """REP1 commission = $50.00 × 5% = $2.50 (order 1002 only)."""
    records = commjob_calc_commission_broken(orders)
    by_rep = commission_by_rep(records)
    assert by_rep.get("REP1", Decimal("0")) == Decimal("2.50"), \
        f"REP1 commission expected $2.50, got {by_rep.get('REP1')}"


def test_commission_rep2_zero():
    """REP2 has no eligible orders at baseline."""
    records = commjob_calc_commission_broken(orders)
    by_rep = commission_by_rep(records)
    assert by_rep.get("REP2", Decimal("0")) == Decimal("0.00")


# ---------------------------------------------------------------------------
# PRICECALC — baseline rounding (HALF_UP)
# ---------------------------------------------------------------------------

def test_pricecalc_no_discount_below_10():
    """Qty < 10: price unchanged. Source: PRICECALC.RPGLE lines 35-38."""
    assert pricecalc_half_up(Decimal("10.00"), 5) == Decimal("10.00")


def test_pricecalc_5pct_discount_at_10():
    """Qty >= 10: 5% discount applied."""
    result = pricecalc_half_up(Decimal("10.00"), 10)
    assert result == Decimal("9.50")


def test_pricecalc_half_up_boundary():
    """HALF_UP: $1.225 rounds to $1.23, not $1.22."""
    result = pricecalc_half_up(Decimal("1.225"), 1)
    assert result == Decimal("1.23"), f"Expected $1.23 (HALF_UP), got {result}"
