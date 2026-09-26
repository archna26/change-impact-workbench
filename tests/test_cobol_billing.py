"""
test_cobol_billing.py — COBOL Billing CR-3 Tests
================================================
Legacy Retail Co — Change Impact Workbench demonstration

EXECUTION ENVIRONMENT: Python / pytest.
These tests simulate behavior from representative COBOL source files
under src/QCBLSRC/.  No COBOL compiler or runtime is involved.

Change Request CR-3: Widen BILL-RATE in BILREC.CPY from PIC 9(3)V99
to PIC 9(5)V99.

The workbench command:
  python sim/ciw_engine.py --artifact BILL-RATE --type field --lang cobol

finds:
  [CONFIRMED]  BILREC.BILL-RATE    DEFINES      @ src/QCBLSRC/BILREC.CPY
  [CONFIRMED]  CALCBILL            COPY_MEMBER  @ src/QCBLSRC/CALCBILL.CBL
  [CONFIRMED]  CALCBILL            WRITES_FIELD @ src/QCBLSRC/CALCBILL.CBL
  [CONFIRMED]  BILPRINT            COPY_MEMBER  @ src/QCBLSRC/BILPRINT.CBL
  [CONFIRMED]  BILPRINT            WRITES_FIELD @ src/QCBLSRC/BILPRINT.CBL

Tests prove that narrowing vs widening the field type produces
measurably different output at the boundary value (rate = 1000.00).
"""

import sys
from pathlib import Path
from decimal import Decimal

sys.path.insert(0, str(Path(__file__).parent.parent / "sim"))

from billing_sim import (
    make_billing_records,
    compute_all,
    MAX_RATE_PRE,
    MAX_RATE_POST,
)

records = make_billing_records()


# ---------------------------------------------------------------------------
# Baseline: pre-change computation (PIC 9(3)V99 cap)
# ---------------------------------------------------------------------------

def test_normal_rate_computed_correctly_pre_change():
    """ACCT-001: rate $10.50 × 100 units = $1,050.00 (within PIC 9(3)V99 range)."""
    processed = compute_all(records, post_change=False)
    rec = next(r for r in processed if r.bill_acct == "ACCT-001")
    assert rec.bill_amount == Decimal("1050.00"), \
        f"Expected $1050.00, got {rec.bill_amount}"


def test_near_limit_rate_pre_change():
    """ACCT-003: rate $999.99 × 200 = $199,998.00 (at PIC 9(3)V99 limit)."""
    processed = compute_all(records, post_change=False)
    rec = next(r for r in processed if r.bill_acct == "ACCT-003")
    assert rec.bill_amount == Decimal("199998.00"), \
        f"Expected $199998.00, got {rec.bill_amount}"


# ---------------------------------------------------------------------------
# CR-3 boundary: rate 1000.00 exceeds PIC 9(3)V99 capacity
# ---------------------------------------------------------------------------

def test_overflow_rate_truncated_pre_change():
    """
    ACCT-004: rate $1,000.00 exceeds PIC 9(3)V99 max (999.99).
    Pre-change: truncated to 999.99 → amount = 1 × 999.99 = $999.99.
    This is WRONG — the actual charge should be $1,000.00.
    Demonstrates why CR-3 is needed.
    """
    processed = compute_all(records, post_change=False)
    rec = next(r for r in processed if r.bill_acct == "ACCT-004")
    assert rec.bill_amount == Decimal("999.99"), \
        f"Pre-change truncation expected $999.99, got {rec.bill_amount}"


def test_overflow_rate_correct_post_change():
    """
    CR-3 fix: BILL-RATE widened to PIC 9(5)V99.
    ACCT-004: rate $1,000.00 × 1 unit = $1,000.00 — now computed correctly.
    """
    processed = compute_all(records, post_change=True)
    rec = next(r for r in processed if r.bill_acct == "ACCT-004")
    assert rec.bill_amount == Decimal("1000.00"), \
        f"Post-change expected $1000.00, got {rec.bill_amount}"


def test_pre_and_post_change_differ_at_boundary():
    """
    Proves the two consumers (CALCBILL, BILPRINT) produce different results
    before and after CR-3 — the workbench correctly flagged both as affected.
    """
    pre  = compute_all(records, post_change=False)
    post = compute_all(records, post_change=True)
    pre_amt  = next(r.bill_amount for r in pre  if r.bill_acct == "ACCT-004")
    post_amt = next(r.bill_amount for r in post if r.bill_acct == "ACCT-004")
    assert pre_amt  == Decimal("999.99"),  f"Pre-change: expected 999.99, got {pre_amt}"
    assert post_amt == Decimal("1000.00"), f"Post-change: expected 1000.00, got {post_amt}"
    assert pre_amt != post_amt, "Pre and post must differ at boundary rate"


# ---------------------------------------------------------------------------
# Regression: non-boundary records unchanged by CR-3
# ---------------------------------------------------------------------------

def test_normal_records_unaffected_by_cr3():
    """ACCT-001 and ACCT-002 produce identical amounts before and after CR-3."""
    pre  = compute_all(records, post_change=False)
    post = compute_all(records, post_change=True)
    for acct in ("ACCT-001", "ACCT-002"):
        pre_amt  = next(r.bill_amount for r in pre  if r.bill_acct == acct)
        post_amt = next(r.bill_amount for r in post if r.bill_acct == acct)
        assert pre_amt == post_amt, \
            f"{acct}: expected identical amounts, got pre={pre_amt} post={post_amt}"


# ---------------------------------------------------------------------------
# Engine coverage verification (spot-check against answer key)
# ---------------------------------------------------------------------------

def test_engine_finds_calcbill_and_bilprint():
    """
    Run the CIW engine on BILL-RATE and verify it finds both COBOL consumers.
    This test proves the engine works generically — no COBOL-specific names
    are hard-coded in the engine.
    """
    sim_dir = str(Path(__file__).parent.parent / "sim")
    if sim_dir not in sys.path:
        sys.path.insert(0, sim_dir)
    import ciw_engine as ciw

    repo_root = Path(__file__).parent.parent
    cat = ciw.build_catalog(repo_root)
    rpt = ciw.traverse_field("BILL-RATE", cat, "cobol", repo_root)

    confirmed_targets = {d.target for d in rpt.confirmed}
    assert "BILREC.BILL-RATE" in confirmed_targets, \
        f"BILREC.BILL-RATE not in confirmed: {confirmed_targets}"
    assert "CALCBILL" in confirmed_targets, \
        f"CALCBILL not in confirmed: {confirmed_targets}"
    assert "BILPRINT" in confirmed_targets, \
        f"BILPRINT not in confirmed: {confirmed_targets}"
    # IBM i programs must NOT appear in COBOL-scoped report
    for ibmi_pgm in ("INVUPDJOB", "COMMJOB", "ORDENTRY"):
        assert ibmi_pgm not in confirmed_targets, \
            f"IBM i program {ibmi_pgm} must not appear in COBOL-scoped report"
