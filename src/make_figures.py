"""Builds paper figures (PNG, 300 dpi) and results tables (Markdown) from results/results.json."""
import json, os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
R = json.load(open(os.path.join(ROOT, "results", "results.json")))
OUT = os.path.join(ROOT, "results"); os.makedirs(OUT, exist_ok=True)
C = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100"]          # categorical slots 1-4, fixed order
INK, MUTED, GRID = "#0b0b0b", "#52514e", "#e4e3df"
METHODS = ["Name-only", "Data-only (IND)", "Fixed-weight fusion", "Proposed (adaptive)"]
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 9, "axes.edgecolor": MUTED,
                     "axes.labelcolor": INK, "xtick.color": MUTED, "ytick.color": MUTED,
                     "axes.spines.top": False, "axes.spines.right": False})

def style(ax, ylabel):
    ax.set_ylabel(ylabel); ax.yaxis.grid(True, color=GRID, lw=0.8); ax.set_axisbelow(True)

def grouped(ax, groups, series, values, ylim=(0, 1.05), fmt="{:.2f}"):
    n = len(series); w = 0.8 / n
    for i, s in enumerate(series):
        xs = [g + (i - (n - 1) / 2) * w for g in range(len(groups))]
        bars = ax.bar(xs, values[i], w * 0.92, color=C[i], label=s, edgecolor="white", linewidth=0.8)
        for x, v in zip(xs, values[i]):
            ax.text(x, v + 0.012, fmt.format(v), ha="center", va="bottom", fontsize=6.5, color=MUTED)
    ax.set_xticks(range(len(groups))); ax.set_xticklabels(groups); ax.set_ylim(*ylim)

# Fig A: detection F1 across all schema sets
groups = ["Chinook", "Northwind", "Sakila", "Synthetic\nmodern", "Synthetic\nlegacy"]
vals = []
for m in METHODS:
    row = [R["public"][g]["detection"][m]["F1"] for g in ["Chinook", "Northwind", "Sakila"]]
    row += [R["synthetic"][p]["detection"][m]["F1"]["mean"] for p in ["modern", "legacy"]]
    vals.append(row)
fig, ax = plt.subplots(figsize=(7.2, 3.2)); grouped(ax, groups, METHODS, vals)
style(ax, "F1 (undeclared dependency recovery)")
ax.legend(ncol=4, frameon=False, loc="upper center", bbox_to_anchor=(0.5, 1.13), fontsize=8)
fig.tight_layout(); fig.savefig(os.path.join(OUT, "fig_detection_f1.png"), dpi=300); plt.close(fig)

# Fig B: recall by naming style (legacy profile)
styles = ["clean", "role", "abbrev", "opaque"]
rb = R["synthetic"]["legacy"]["recall_by_style"]
vals = [[rb[m][s] for s in styles] for m in METHODS]
fig, ax = plt.subplots(figsize=(7.2, 3.0))
grouped(ax, ["Clean\n(CUST_NO)", "Role-qualified\n(OWNER_CUST_NO)", "Abbreviated\n(CST_NO)", "Opaque\n(XREF_CD3)"], METHODS, vals)
style(ax, "Recall"); ax.legend(ncol=4, frameon=False, loc="upper center", bbox_to_anchor=(0.5, 1.14), fontsize=8)
fig.tight_layout(); fig.savefig(os.path.join(OUT, "fig_recall_by_style.png"), dpi=300); plt.close(fig)

# Fig C: rows successfully loaded under each migration plan
plans = ["No graph (alphabetical)", "Graph: Name-only", "Graph: Proposed", "Oracle (declared FKs)"]
labels = ["No graph", "Graph (name-only)", "Graph (proposed)", "Oracle (true FKs)"]
groups = ["Chinook", "Northwind", "Synthetic\nlegacy"]
vals = []
for p in plans:
    row = []
    for g in ["Chinook", "Northwind"]:
        m = R["public"][g]["migration"][p]; row.append(m["loaded"] / (m["loaded"] + m["rejected"]))
    m = R["synthetic"]["legacy"]["migration"][p]; row.append(m["loaded"] / (m["loaded"] + m["rejected"]))
    vals.append(row)
fig, ax = plt.subplots(figsize=(7.2, 3.0)); grouped(ax, groups, labels, vals, fmt="{:.0%}")
style(ax, "Rows loaded (FK-enforced target)")
ax.yaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1.0))
ax.legend(ncol=4, frameon=False, loc="upper center", bbox_to_anchor=(0.5, 1.14), fontsize=8)
fig.tight_layout(); fig.savefig(os.path.join(OUT, "fig_rows_loaded.png"), dpi=300); plt.close(fig)

# Fig D: scalability (detection time vs schema size) — single series
S = R["scalability"]
fig, ax = plt.subplots(figsize=(3.5, 2.8))
ax.plot([s["columns"] for s in S], [s["detect_s"] for s in S], color=C[0], lw=2, marker="o", ms=5)
for s in S[-2:]:
    ax.annotate(f'{s["tables"]} tables\n{s["detect_s"]:.0f}s', (s["columns"], s["detect_s"]),
                textcoords="offset points", xytext=(-8, 6), ha="right", fontsize=7, color=MUTED)
ax.set_xlabel("Columns profiled"); style(ax, "Dependency detection time (s)")
fig.tight_layout(); fig.savefig(os.path.join(OUT, "fig_scalability.png"), dpi=300); plt.close(fig)

# Fig E: alpha sensitivity (legacy + modern), two series
fig, ax = plt.subplots(figsize=(3.5, 2.8))
for i, p in enumerate(["modern", "legacy"]):
    a = R["synthetic"][p]["alpha_sensitivity"]; xs = [float(k) for k in a]; ys = list(a.values())
    ax.plot(xs, ys, color=C[i], lw=2, marker="o", ms=4, label=f"Synthetic {p}")
    ax.text(xs[-1] + 0.02, ys[-1], p, fontsize=7, color=MUTED, va="center")
ax.axvline(R["params"]["adaptive"]["alpha"], color=MUTED, lw=0.8, ls="--")
ax.set_xlabel("α (weight on name evidence)"); style(ax, "F1"); ax.set_ylim(0.6, 1.02)
ax.legend(frameon=False, fontsize=7, loc="lower right")
fig.tight_layout(); fig.savefig(os.path.join(OUT, "fig_alpha_sensitivity.png"), dpi=300); plt.close(fig)

# Tables (Markdown)
L = ["# Results tables\n", "## Table 1. Undeclared-dependency detection (all FK constraints hidden)\n",
     "| Schema set | Method | Precision | Recall | F1 |", "|---|---|---|---|---|"]
for g in ["Chinook", "Northwind", "Sakila"]:
    for m in METHODS:
        d = R["public"][g]["detection"][m]
        L.append(f"| {g} ({R['public'][g]['true_deps']} deps) | {m} | {d['P']:.3f} | {d['R']:.3f} | {d['F1']:.3f} |")
for p in ["modern", "legacy"]:
    for m in METHODS:
        d = R["synthetic"][p]["detection"][m]
        L.append(f"| Synthetic {p} (5×100 tables) | {m} | {d['P']['mean']:.3f} ± {d['P']['sd']:.3f} | "
                 f"{d['R']['mean']:.3f} ± {d['R']['sd']:.3f} | {d['F1']['mean']:.3f} ± {d['F1']['sd']:.3f} |")
L += ["\n## Table 2. Recall by naming style (synthetic legacy)\n",
      "| Method | " + " | ".join(styles + ["self"]) + " |", "|---|" + "---|" * 5]
for m in METHODS:
    L.append(f"| {m} | " + " | ".join(f"{rb[m][s]:.2f}" for s in styles + ["self"]) + " |")
L.append("\nDependencies per style (5 seeds): " + ", ".join(f"{k}={v}" for k, v in R["synthetic"]["legacy"]["style_counts"].items()))
L += ["\n## Table 3. Migration execution (target with FK constraints enforced)\n",
      "| Schema | Plan | Ordering score Sq | Rows loaded | Rows rejected | Waves | Cycles | Speedup (4 workers, model) |",
      "|---|---|---|---|---|---|---|---|"]
for g in ["Chinook", "Northwind", "Sakila"]:
    for p in plans:
        m = R["public"][g]["migration"][p]
        L.append(f"| {g} | {p} | {m['Sq']:.3f} | {m['loaded']:,} | {m['rejected']:,} | {m['waves']} | {m['cycles']} | {m['speedup4']:.2f}× |")
for pr in ["modern", "legacy"]:
    for p in plans:
        m = R["synthetic"][pr]["migration"][p]
        L.append(f"| Synthetic {pr} (mean of 5) | {p} | {m['Sq']:.3f} | {m['loaded']:,.0f} | {m['rejected']:,.0f} | {m['waves']:.1f} | {m['cycles']:.1f} | {m['speedup4']:.2f}× |")
L.append("\nSynthetic data contains ~2% planted orphan rows (legacy data-quality defects); the oracle row shows that floor.")
L += ["\n## Table 4. Scalability (synthetic legacy, proposed method)\n",
      "| Tables | Columns | True deps | KG nodes | KG edges | Extract (s) | Detect (s) | Plan (s) | F1 | Speedup 4w | Speedup 8w |",
      "|---|---|---|---|---|---|---|---|---|---|---|"]
for s in S:
    L.append(f"| {s['tables']} | {s['columns']:,} | {s['true_deps']:,} | {s['graph_nodes']:,} | {s['graph_edges']:,} | "
             f"{s['extract_s']:.2f} | {s['detect_s']:.1f} | {s['plan_s']:.3f} | {s['F1']:.3f} | {s['speedup4']:.2f}× | {s['speedup8']:.2f}× |")
L.append(f"\nTuned parameters (dev seeds 101–103 only): {json.dumps(R['params']['adaptive'])}")
open(os.path.join(OUT, "tables.md"), "w").write("\n".join(L) + "\n")
print("figures and tables written to", OUT)
