import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from risk import SNAPSHOT, par, prepare  # noqa: E402


def _loans():
    return pd.DataFrame([
        # healthy active loan: outstanding 50k
        dict(loan_id="A", customer_id="c", disbursed_date="2025-05-01", principal_ngn=100_000, tenor_months=1, monthly_rate=0.0,
             due_date="2025-07-30", status="active", first_missed_date=None, amount_repaid_ngn=50_000),
        # 100 days past due, outstanding 100k
        dict(loan_id="B", customer_id="c", disbursed_date="2025-01-01", principal_ngn=100_000, tenor_months=3, monthly_rate=0.0,
             due_date="2025-04-01", status="delinquent", first_missed_date=(SNAPSHOT - pd.Timedelta(days=100)).strftime("%Y-%m-%d"),
             amount_repaid_ngn=0),
        # repaid - contributes nothing
        dict(loan_id="C", customer_id="c", disbursed_date="2025-01-01", principal_ngn=100_000, tenor_months=1, monthly_rate=0.0,
             due_date="2025-02-01", status="repaid", first_missed_date=None, amount_repaid_ngn=100_000),
    ])


def test_outstanding_and_dpd():
    d = prepare(_loans()).set_index("loan_id")
    assert d.loc["A", "outstanding"] == 50_000
    assert d.loc["C", "outstanding"] == 0
    assert d.loc["B", "dpd"] == 100


def test_par_buckets():
    d = prepare(_loans())
    assert par(d, 30) == pytest.approx(100_000 / 150_000)
    assert par(d, 90) == pytest.approx(100_000 / 150_000)
    assert par(d, 120) == 0
