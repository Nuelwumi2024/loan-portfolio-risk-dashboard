"""Credit-risk metric definitions (kept separate from plotting so they are unit-testable).

Definitions
-----------
* DPD (days past due) = snapshot - first_missed_date, for loans that have missed a payment.
* Outstanding = principal*(1 + monthly_rate*tenor) - amount_repaid, floored at 0, for non-repaid loans.
* PAR-N  (portfolio at risk) = outstanding of loans with DPD > N  /  total outstanding.
* NPL ratio = PAR-90 (a common proxy; regulators/banks may define it differently).
"""
from __future__ import annotations

import pandas as pd

SNAPSHOT = pd.Timestamp("2025-06-30")


def prepare(loans: pd.DataFrame, snapshot: pd.Timestamp = SNAPSHOT) -> pd.DataFrame:
    d = loans.copy()
    for c in ("disbursed_date", "due_date", "first_missed_date"):
        d[c] = pd.to_datetime(d[c])
    d["total_due"] = d["principal_ngn"] * (1 + d["monthly_rate"] * d["tenor_months"])
    d["outstanding"] = (d["total_due"] - d["amount_repaid_ngn"]).clip(lower=0)
    d.loc[d["status"] == "repaid", "outstanding"] = 0.0
    d["dpd"] = (snapshot - d["first_missed_date"]).dt.days.where(d["first_missed_date"].notna(), 0).clip(lower=0)
    d["vintage"] = d["disbursed_date"].dt.to_period("M").dt.to_timestamp()
    return d


def par(d: pd.DataFrame, days: int) -> float:
    total = d["outstanding"].sum()
    return float(d.loc[d["dpd"] > days, "outstanding"].sum() / total) if total else 0.0


def default_rate(d: pd.DataFrame, by: str) -> pd.DataFrame:
    g = d.groupby(by, observed=True).agg(loans=("loan_id", "count"), bad=("dpd", lambda s: (s > 0).sum()))
    g["bad_rate"] = g["bad"] / g["loans"]
    return g.reset_index()


def vintage_curves(d: pd.DataFrame, max_mob: int = 12) -> pd.DataFrame:
    """Cumulative share of each monthly vintage that has missed a payment by month-on-book k."""
    rows = []
    for v, g in d.groupby("vintage"):
        age = int((SNAPSHOT - v).days // 30)
        for k in range(1, min(age, max_mob) + 1):
            missed_by_k = ((g["first_missed_date"] - g["disbursed_date"]).dt.days <= k * 30).sum()
            rows.append({"vintage": v, "mob": k, "cum_miss_rate": missed_by_k / len(g)})
    return pd.DataFrame(rows)
