"""Three source-bound displays; all cutoff and series cases remain visible."""

from pathlib import Path
import csv
import hashlib
import json
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
POLICIES = ["day_ahead", "same_day_noon", "end_of_day"]
COLORS = ["#173b56", "#bd6b24", "#7e6b91"]
LABELS = ["Prior-day noon · eligible", "Same-day noon · late", "End of day · late"]
plt.rcParams.update(
    {
        "font.family": "DejaVu Sans",
        "font.size": 10,
        "svg.fonttype": "none",
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.spines.left": False,
        "axes.edgecolor": "#69727a",
        "text.color": "#152c3b",
        "axes.labelcolor": "#152c3b",
        "xtick.color": "#344b5c",
        "ytick.color": "#344b5c",
    }
)
LEDGER = []


def read(name):
    return list(
        csv.DictReader((ROOT / "results" / name).open(encoding="utf-8", newline=""))
    )


def bar(ax, ident, x, y, width, height, value, orientation, source):
    if orientation == "v":
        patch = ax.bar(
            x, value, width=width, color=COLORS[POLICIES.index(source["policy"])]
        )[0]
        label = ax.text(
            x,
            value + 30,
            f"{value:.1f}",
            ha="center",
            va="bottom",
            fontsize=12,
            fontweight="bold",
        )
    else:
        patch = ax.barh(
            y, value, height=height, color=COLORS[POLICIES.index(source["policy"])]
        )[0]
        label = ax.text(
            value + (22 if source["field"] == "mae_mw" else 0.10),
            y,
            f"{value:.1f}",
            va="center",
            fontsize=8.2,
        )
    patch.set_gid("bar_" + ident)
    label.set_gid("label_" + ident)
    LEDGER.append(dict(id=ident, value=value, orientation=orientation, source=source))


def save(fig, name):
    for ext in ["pdf", "svg", "png"]:
        target = ROOT / "figures" / (name + "." + ext)
        fig.savefig(target, dpi=160, facecolor="white")
        if ext == "svg":
            target.write_bytes(
                b"\n".join(line.rstrip() for line in target.read_bytes().splitlines())
                + b"\n"
            )
    plt.close(fig)


overall = read("overall_metrics.csv")
daily = read("daily_metrics.csv")
fig, ax = plt.subplots(figsize=(7.1, 3.9))
fig.subplots_adjust(left=0.13, right=0.98, bottom=0.29, top=0.80)
ax.set_gid("audit_axes")
ax.set_xlim(-0.6, 2.6)
ax.set_ylim(0, 1200)
ax.set_yticks([0, 300, 600, 900, 1200])
ax.set_ylabel("System MAE (MW)")
for i, policy in enumerate(POLICIES):
    r = next(r for r in overall if r["zone"] == "SystemTotal" and r["policy"] == policy)
    bar(
        ax,
        "overall_" + str(i),
        i,
        0,
        0.58,
        0,
        float(r["mae_mw"]),
        "v",
        dict(
            file="overall_metrics.csv",
            zone="SystemTotal",
            policy=policy,
            field="mae_mw",
        ),
    )
ax.set_xticks(
    range(3), ["Prior-day noon\neligible", "Same-day noon\nlate", "End of day\nlate"]
)
ax.set_axisbelow(True)
ax.grid(axis="y", color="#e3e8ec")
fig.text(
    0.13,
    0.94,
    "A smaller retrospective error can use a later file",
    fontsize=14,
    fontweight="bold",
)
fig.text(
    0.13,
    0.86,
    "120 system hours · 25–29 October 2026 · all three fixed cutoffs",
    fontsize=10,
)
fig.text(
    0.13,
    0.105,
    "Both same-day files miss the prior-day deadline for all 120 hours.",
    fontsize=9,
)
fig.text(
    0.13,
    0.055,
    "End-of-day files were posted after 115 target intervals had already ended.",
    fontsize=9,
)
save(fig, "system_cutoffs")

days = json.loads((ROOT / "data/source_plan.json").read_bytes())["days"]
fig, ax = plt.subplots(figsize=(7.1, 4.4))
fig.subplots_adjust(left=0.13, right=0.95, bottom=0.31, top=0.81)
ax.set_gid("audit_axes")
ax.set_xlim(0, 1800)
ax.set_ylim(-0.6, 4.6)
ax.invert_yaxis()
ax.set_xticks([0, 300, 600, 900, 1200, 1500, 1800])
ax.set_xlabel("Daily system MAE (MW)")
for j, day in enumerate(days):
    for i, policy in enumerate(POLICIES):
        r = next(
            r
            for r in daily
            if r["day"] == day and r["zone"] == "SystemTotal" and r["policy"] == policy
        )
        bar(
            ax,
            "daily_" + str(j) + "_" + str(i),
            0,
            j + (i - 1) * 0.24,
            0,
            0.21,
            float(r["mae_mw"]),
            "h",
            dict(
                file="daily_metrics.csv",
                day=day,
                zone="SystemTotal",
                policy=policy,
                field="mae_mw",
            ),
        )
ax.set_yticks(range(5), ["Oct " + x[-2:] for x in days])
ax.set_axisbelow(True)
ax.grid(axis="x", color="#e3e8ec")
fig.text(
    0.13,
    0.94,
    "The later file does not lower error on every day",
    fontsize=14,
    fontweight="bold",
)
fig.text(
    0.13,
    0.865,
    "Each bar covers the same 24 system hours; five adjacent days are dependent.",
    fontsize=9,
)
handles = [plt.Rectangle((0, 0), 1, 1, color=c) for c in COLORS]
fig.legend(
    handles,
    LABELS,
    loc="lower center",
    bbox_to_anchor=(0.5, 0.02),
    ncol=1,
    frameon=False,
    fontsize=8.5,
)
save(fig, "daily_system_errors")

zones = json.loads((ROOT / "data/source_plan.json").read_bytes())["zones"]
fig, ax = plt.subplots(figsize=(7.1, 5.7))
fig.subplots_adjust(left=0.23, right=0.95, bottom=0.20, top=0.84)
ax.set_gid("audit_axes")
ax.set_xlim(0, 9.5)
ax.set_ylim(-0.6, 8.6)
ax.invert_yaxis()
ax.set_xticks([0, 2, 4, 6, 8])
ax.set_xlabel("WAPE (% of summed positive actual load)")
for j, zone in enumerate(zones):
    for i, policy in enumerate(POLICIES):
        r = next(r for r in overall if r["zone"] == zone and r["policy"] == policy)
        bar(
            ax,
            "zone_" + str(j) + "_" + str(i),
            0,
            j + (i - 1) * 0.24,
            0,
            0.21,
            100 * float(r["wape"]),
            "h",
            dict(
                file="overall_metrics.csv",
                zone=zone,
                policy=policy,
                field="wape",
                scale=100,
            ),
        )
ax.set_yticks(
    range(9),
    [
        "Coast",
        "East",
        "Far West",
        "North",
        "North Central",
        "South Central",
        "Southern",
        "West",
        "System total",
    ],
)
ax.set_axisbelow(True)
ax.grid(axis="x", color="#e3e8ec")
fig.text(
    0.08,
    0.95,
    "System totals conceal differences between zones",
    fontsize=14,
    fontweight="bold",
)
fig.text(
    0.08,
    0.90,
    "120 hours per series · all 27 fixed series/cutoff combinations",
    fontsize=10,
)
fig.legend(
    handles,
    LABELS,
    loc="lower center",
    bbox_to_anchor=(0.5, 0.005),
    ncol=1,
    frameon=False,
    fontsize=8.5,
)
save(fig, "all_series_wape")

assets = {
    str(p.relative_to(ROOT))
    .replace("\\", "/"): hashlib.sha256(p.read_bytes())
    .hexdigest()
    for p in (ROOT / "figures").glob("*")
    if p.suffix in [".pdf", ".svg", ".png"]
}
(ROOT / "figures/ledger.json").write_bytes(
    (json.dumps(dict(bars=LEDGER, assets_sha256=assets), indent=2) + "\n").encode()
)
print("FIGURES_CREATED", len(LEDGER), "source-bound bars", len(assets), "assets")
