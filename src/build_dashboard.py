"""Build a self-contained HTML risk dashboard: python src/build_dashboard.py  ->  dashboard.html"""
from __future__ import annotations

import base64
import io
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

from risk import SNAPSHOT, default_rate, par, prepare, vintage_curves  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
BLUE, RED, GREY = "#1f5fbf", "#d1342f", "#9aa3ad"
plt.rcParams.update({"axes.spines.top": False, "axes.spines.right": False, "font.size": 10,
                     "axes.titleweight": "bold", "figure.dpi": 120})

(ROOT / "figures").mkdir(exist_ok=True)
loans = pd.read_csv(ROOT / "data/raw/loans.csv")
cust = pd.read_csv(ROOT / "data/raw/customers.csv")[["customer_id", "kyc_tier", "acquisition_channel"]]
d = prepare(loans).merge(cust, on="customer_id")
d["ticket"] = pd.cut(d["principal_ngn"], [0, 20_000, 50_000, 100_000, 200_000, 1e9],
                     labels=["20k", "50k", "100k", "200k", "500k"])
d["tenor"] = d["tenor_months"].astype(str) + "m"

png = lambda fig: "data:image/png;base64," + base64.b64encode((lambda b: (fig.savefig(b, format="png", bbox_inches="tight"), b.getvalue())[1])(io.BytesIO())).decode()  # noqa: E731

# --- KPIs
out = d["outstanding"].sum()
kpis = [("Loans disbursed", f"{len(d):,}"), ("Outstanding book", f"NGN {out/1e6:,.1f}m"),
        ("PAR 30", f"{par(d,30)*100:.1f}%"), ("PAR 90 (NPL proxy)", f"{par(d,90)*100:.1f}%")]

# --- Chart 1: PAR buckets
fig, ax = plt.subplots(figsize=(5, 3.2))
vals = [par(d, n) * 100 for n in (0, 30, 60, 90)]
ax.bar(["PAR 1+", "PAR 30", "PAR 60", "PAR 90"], vals, color=[GREY, BLUE, BLUE, RED])
for i, v in enumerate(vals):
    ax.text(i, v + 0.1, f"{v:.1f}%", ha="center", fontweight="bold")
ax.set_ylabel("% of outstanding book"); ax.set_title("Portfolio at risk by delinquency bucket")
fig.savefig(ROOT / 'figures' / 'par_buckets.png', bbox_inches='tight'); c1 = png(fig); plt.close(fig)

# --- Chart 2: vintage curves
vc = vintage_curves(d)
fig, ax = plt.subplots(figsize=(5.6, 3.2))
vint = sorted(vc["vintage"].unique())
for v, g in vc.groupby("vintage"):
    recent = v >= vint[-6]
    ax.plot(g["mob"], g["cum_miss_rate"] * 100, color=BLUE if recent else GREY, lw=1.8 if recent else 0.9, alpha=0.9)
ax.set_xlabel("Months on book"); ax.set_ylabel("% of vintage missed a payment")
ax.set_title("Vintage curves (blue = last 6 vintages)")
fig.savefig(ROOT / 'figures' / 'vintage_curves.png', bbox_inches='tight'); c2 = png(fig); plt.close(fig)

# --- Chart 3: segment default rates
fig, axes = plt.subplots(1, 3, figsize=(11, 3.2), sharey=True)
overall = (d["dpd"] > 0).mean()
for ax, col, title in zip(axes, ("tenor", "ticket", "kyc_tier"), ("Tenor", "Loan size (NGN)", "KYC tier")):
    s = default_rate(d, col)
    ax.bar(s[col].astype(str), s["bad_rate"] * 100, color=[RED if r > overall * 1.25 else GREY for r in s["bad_rate"]])
    ax.axhline(overall * 100, ls="--", color=BLUE, lw=1)
    ax.set_title(title)
axes[0].set_ylabel("% ever delinquent")
fig.savefig(ROOT / 'figures' / 'segment_default_rates.png', bbox_inches='tight'); c3 = png(fig); plt.close(fig)

worst = {c: default_rate(d, c).sort_values("bad_rate").iloc[-1] for c in ("tenor", "ticket", "kyc_tier", "acquisition_channel")}
insights = [
    f"PAR 30 is <b>{par(d,30)*100:.1f}%</b> and PAR 90 is <b>{par(d,90)*100:.1f}%</b> of a NGN {out/1e6:,.1f}m outstanding book as at {SNAPSHOT:%d %b %Y}.",
    f"Highest delinquency: KYC tier <b>{int(worst['kyc_tier'].kyc_tier)}</b> ({worst['kyc_tier'].bad_rate*100:.1f}%), channel <b>{worst['acquisition_channel'].acquisition_channel}</b> "
    f"({worst['acquisition_channel'].bad_rate*100:.1f}%) vs {overall*100:.1f}% portfolio average.",
    f"The riskiest loan size is NGN {worst['ticket'].ticket} ({worst['ticket'].bad_rate*100:.1f}% delinquency) - review underwriting and limits for first-time borrowers in this band.",
    "Recent vintages are still seasoning, so their curves understate eventual loss - re-read monthly rather than concluding early.",
]
tiles = "".join(f'<div class="tile"><div class="k">{k}</div><div class="v">{v}</div></div>' for k, v in kpis)
li = "".join(f"<li>{i}</li>" for i in insights)
html = f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Loan Portfolio Risk Dashboard</title>
<style>body{{font-family:system-ui,Segoe UI,Arial;margin:0;background:#f6f7f9;color:#1b2430}}
.wrap{{max-width:1100px;margin:auto;padding:24px 16px}}h1{{margin:0 0 4px}}.sub{{color:#5b6673;margin-bottom:18px}}
.tiles{{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:12px}}
.tile,.card{{background:#fff;border-radius:10px;padding:14px 16px;box-shadow:0 1px 3px rgba(0,0,0,.08)}}
.k{{color:#5b6673;font-size:13px}}.v{{font-size:26px;font-weight:700}}
.row{{display:grid;grid-template-columns:repeat(auto-fit,minmax(320px,1fr));gap:12px;margin-top:12px}}img{{max-width:100%}}
ul{{line-height:1.6}}</style></head><body><div class="wrap">
<h1>Loan Portfolio Risk Dashboard</h1><div class="sub">Snapshot {SNAPSHOT:%d %B %Y} - synthetic digital-lending book</div>
<div class="tiles">{tiles}</div>
<div class="row"><div class="card"><img src="{c1}"></div><div class="card"><img src="{c2}"></div></div>
<div class="card" style="margin-top:12px"><img src="{c3}"></div>
<div class="card" style="margin-top:12px"><h3>What the data says</h3><ul>{li}</ul></div>
</div></body></html>"""
(ROOT / "dashboard.html").write_text(html, encoding="utf-8")
print("wrote dashboard.html")
print("\n".join(f"{k}: {v}" for k, v in kpis)); print(insights)

