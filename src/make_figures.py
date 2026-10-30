"""Builds every figure and table of the paper from results/results.json (one source).

Outputs
  results/figures/*.pdf, *.png   figures (vector PDF for the paper, PNG for the README)
  results/latex/*.tex            LaTeX tables, \\input by the paper
  results/latex/numbers.tex      LaTeX macros for numbers quoted in the text
  results/tables.md              the same tables in Markdown
"""
import json, os, statistics as st
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
R = json.load(open(os.environ.get("RESULTS", os.path.join(ROOT, "results", "results.json"))))
FIG = os.path.join(ROOT, "results", "figures"); TEX = os.path.join(ROOT, "results", "latex")
os.makedirs(FIG, exist_ok=True); os.makedirs(TEX, exist_ok=True)

C = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#6250d6"]      # categorical slots, fixed order
INK, MUTED, GRID = "#0b0b0b", "#52514e", "#e4e3df"
HATCH = ["", "///", "", "...", "xx"]
serif = [f for f in ("Liberation Serif", "Times New Roman", "DejaVu Serif")
         if any(f in x.name for x in matplotlib.font_manager.fontManager.ttflist)]
plt.rcParams.update({"font.family": serif[0] if serif else "serif", "font.size": 8, "pdf.fonttype": 42,
                     "axes.edgecolor": MUTED, "axes.labelcolor": INK, "xtick.color": MUTED,
                     "ytick.color": MUTED, "axes.spines.top": False, "axes.spines.right": False})

PUB = ["Chinook", "Northwind", "Sakila", "TPC-DS"]
SYN = ["SynthModern-100", "SynthLegacy-100"]
RULES = ["Name-only", "Data-only (IND)", "Fixed-weight fusion", "Proposed (adaptive)"]
CLFS = ["Classifier (exact IND)", "Classifier (partial IND)"]
ABL = ["Proposed (adaptive)", "Proposed without adaptive rule", "Proposed without specificity"]
SHORT = {"Name-only": "Name-only", "Data-only (IND)": "Data-only", "Fixed-weight fusion": "Fixed fusion",
         "Proposed (adaptive)": "Proposed", "Classifier (exact IND)": "Classifier (exact)",
         "Classifier (partial IND)": "Classifier (partial)",
         "Proposed without adaptive rule": "-- adaptive rule", "Proposed without specificity": "-- specificity",
         "Proposed + key inference": "Proposed + key inference"}
PLANS = ["No graph (alphabetical)", "Graph: Name-only", "Graph: Proposed", "Oracle (true dependencies)"]
PLAN_LBL = ["No graph", "Name-only graph", "Proposed graph", "Ground-truth plan"]   # plan from the true dependencies

def det(ds, m, k="F1"):
    """Detection metric; synthetic values are means (with sd available)."""
    if ds in R["public"]:
        return R["public"][ds]["detection"][m][k]
    return R["synthetic"][ds]["detection"][m][k]["mean"]

def sd(ds, m, k="F1"):
    return R["synthetic"][ds]["detection"][m][k]["sd"]

def mig(ds, p):
    return (R["public"][ds] if ds in R["public"] else R["synthetic"][ds])["migration"][p]

def val(ds):
    return (R["public"][ds] if ds in R["public"] else R["synthetic"][ds])["validation"]

def save(fig, name):
    fig.savefig(os.path.join(FIG, name + ".pdf")); fig.savefig(os.path.join(FIG, name + ".png"), dpi=300)
    plt.close(fig)

def style(ax, ylabel):
    ax.set_ylabel(ylabel); ax.yaxis.grid(True, color=GRID, lw=0.6); ax.set_axisbelow(True)

def grouped(ax, groups, series, values, ylim=(0, 1.08), fmt="{:.2f}", labels=True):
    n = len(series); w = 0.82 / n
    for i, s in enumerate(series):
        xs = [g + (i - (n - 1) / 2) * w for g in range(len(groups))]
        ax.bar(xs, values[i], w * 0.9, color=C[i], label=s, edgecolor="white", linewidth=0.6, hatch=HATCH[i])
        if labels:
            for x, v in zip(xs, values[i]):
                lab = fmt.format(v)
                if lab.startswith("0."): lab = lab[1:]
                ax.text(x, v + 0.012, lab, ha="center", va="bottom", fontsize=5, color=MUTED, rotation=90)
    ax.set_xticks(range(len(groups))); ax.set_xticklabels(groups); ax.set_ylim(*ylim)

def legend(ax, n, y=1.16):
    ax.legend(ncol=n, frameon=False, loc="upper center", bbox_to_anchor=(0.5, y), fontsize=7)

# ------------------------------------------------------------------ figures
DS = PUB + SYN
dlabels = [d.replace("-1", "-\n1") for d in DS]
FIGM = RULES + ["Classifier (partial IND)"]
fig, ax = plt.subplots(figsize=(7.16, 2.9))
grouped(ax, dlabels, [SHORT[m] for m in FIGM], [[det(d, m) for d in DS] for m in FIGM], ylim=(0, 1.15))
style(ax, "F1"); legend(ax, 5); fig.tight_layout(); save(fig, "fig_detection_f1")

styles = ["clean", "role", "abbrev", "opaque"]
rb = R["synthetic"]["SynthLegacy-100"]["recall_by_style"]
fig, ax = plt.subplots(figsize=(7.16, 2.6))
grouped(ax, ["Clean", "Role-qualified", "Abbreviated", "Opaque"], [SHORT[m] for m in FIGM],
        [[rb[m][s] for s in styles] for m in FIGM], ylim=(0, 1.15))
style(ax, "Recall"); legend(ax, 5); fig.tight_layout(); save(fig, "fig_recall_by_style")

fig, ax = plt.subplots(figsize=(7.16, 2.6))
vals = [[mig(d, p)["exact"] / mig(d, p)["source_rows"] for d in DS] for p in PLANS]
grouped(ax, dlabels, PLAN_LBL, vals, fmt="{:.0%}", ylim=(0, 1.15))
ax.yaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1.0))
style(ax, "Rows migrated exactly"); legend(ax, 4); fig.tight_layout(); save(fig, "fig_rows_exact")

SC = R["scalability"]["rows"]
fig, ax = plt.subplots(figsize=(3.5, 2.5))
xs = [s["columns"] for s in SC]; med = [s["detect_s"]["median"] for s in SC]
lo = [m - s["detect_s"]["min"] for m, s in zip(med, SC)]; hi = [s["detect_s"]["max"] - m for m, s in zip(med, SC)]
ax.errorbar(xs, med, yerr=[lo, hi], color=C[0], lw=1.5, marker="o", ms=4, capsize=2)
for s in SC[-2:]:
    ax.annotate(f'{s["tables"]:,} tables: {s["detect_s"]["median"]:.0f} s', (s["columns"], s["detect_s"]["median"]),
                textcoords="offset points", xytext=(-6, 4), ha="right", fontsize=6.5, color=MUTED)
ax.set_xlabel("Columns profiled"); style(ax, f"Detection time (s), median of {R['scalability']['repetitions']}")
fig.tight_layout(); save(fig, "fig_scalability")

fig, ax = plt.subplots(figsize=(3.5, 2.5))
for i, p in enumerate(SYN):
    a = R["synthetic"][p]["alpha_sensitivity"]
    ax.plot([float(k) for k in a], list(a.values()), color=C[i], lw=1.5, marker="o", ms=3.5, label=p)
ax.axvline(R["params"]["adaptive"]["alpha"], color=MUTED, lw=0.7, ls="--")
ax.set_xlabel(r"$\alpha$ (weight on naming evidence)"); style(ax, "F1"); ax.set_ylim(0.6, 1.02)
ax.legend(frameon=False, fontsize=6.5, loc="lower right"); fig.tight_layout(); save(fig, "fig_alpha_sensitivity")

ST = R["stress"]; snames = list(ST)
slabels = ["Baseline", "Orphans\n10%", "Orphans\n25%", "NULL\n30%", "Integer\nkeys", "No PK\n20%", "Composite\nkeys", "Combined"]
fig, ax = plt.subplots(figsize=(7.16, 2.6))
grouped(ax, slabels, [SHORT[m] for m in FIGM],
        [[ST[s]["detection"][m]["F1"]["mean"] for s in snames] for m in FIGM], ylim=(0, 1.15))
style(ax, "F1"); legend(ax, 5); fig.tight_layout(); save(fig, "fig_stress")

# ------------------------------------------------------------------ LaTeX tables
def f3(x): return f"{x:.3f}"
def pct(x): return f"{100 * x:.1f}\\%"
def n0(x): return f"{x:,.0f}"
def wr(name, body): open(os.path.join(TEX, name + ".tex"), "w").write(body)
md = []   # markdown mirror

def resize(tab): return "\\resizebox{\\linewidth}{!}{%\n" + tab + "}\n"   # scales to the float (column or page width)

# datasets
rows = []
for d in PUB:
    r = R["public"][d]
    rows.append(f"{d} & {r['tables']} & {r['columns']} & {n0(r['rows'])} & {r['true_deps']} & {n0(r['type_compatible_pairs'])} & {n0(r['candidates_after_blocking'])} \\\\")
for d in SYN:
    r = R["synthetic"][d]; dc = r["style_counts"]
    rows.append(f"{d} & 100 & -- & -- & {sum(dc.values()) / 5:.1f} & {n0(r['candidates']['type_compatible_pairs'])} & {n0(r['candidates']['candidates_after_blocking'])} \\\\")
wr("tab_datasets", resize("\\begin{tabular}{lrrrrrr}\n\\toprule\nDataset & Tables & Columns & Rows & Deps. & Pairs & Candidates \\\\\n\\midrule\n"
                          + "\n".join(rows) + "\n\\bottomrule\n\\end{tabular}\n"))

# detection
rows = []
for d in DS:
    ms = RULES + CLFS
    best = max(det(d, m) for m in ms)
    for i, m in enumerate(ms):
        name = (d.replace("-1", "-\\\\1") if False else d) if i == 0 else ""
        if d in R["public"]:
            vals_ = [f3(det(d, m, k)) for k in ("P", "R")] + [f3(det(d, m))]
        else:
            vals_ = [f"{det(d, m, k):.3f}$\\pm${sd(d, m, k):.3f}".replace("0.", ".", 1) if False else
                     f"{det(d, m, k):.3f}$\\pm${sd(d, m, k):.3f}" for k in ("P", "R", "F1")]
        if abs(det(d, m) - best) < 1e-12:
            vals_[-1] = "\\textbf{" + vals_[-1] + "}"
        rows.append(f"{name} & {SHORT[m]} & " + " & ".join(vals_) + " \\\\")
    rows.append("\\midrule")
rows = rows[:-1]
wr("tab_detection", resize("\\begin{tabular}{llccc}\n\\toprule\nDataset & Method & Precision & Recall & F1 \\\\\n\\midrule\n"
                           + "\n".join(rows) + "\n\\bottomrule\n\\end{tabular}\n"))

# ablation
ABD = ["Northwind", "TPC-DS", "SynthModern-100", "SynthLegacy-100"]
rows = [f"{SHORT[m]} & " + " & ".join(f3(det(d, m)) for d in ABD) + " \\\\" for m in ABL]
rows[0] = rows[0].replace("Proposed", "Proposed (full)")
wr("tab_ablation", resize("\\begin{tabular}{lcccc}\n\\toprule\nVariant & Northwind & TPC-DS & SynthModern & SynthLegacy \\\\\n\\midrule\n"
                          + "\n".join(rows) + "\n\\bottomrule\n\\end{tabular}\n"))

# style recall
rows = [f"{SHORT[m]} & " + " & ".join(f"{rb[m][s]:.2f}" for s in styles + ["self"]) + " \\\\" for m in RULES + CLFS]
wr("tab_style", resize("\\begin{tabular}{lccccc}\n\\toprule\nMethod & Clean & Role & Abbrev. & Opaque & Self \\\\\n\\midrule\n"
                       + "\n".join(rows) + "\n\\bottomrule\n\\end{tabular}\n"))

# migration: initial vs exact
rows = []
for d in DS:
    cells = []
    for p in PLANS:
        m = mig(d, p); cells.append(f"{pct(m['initially_loaded'] / m['source_rows'])} / {pct(m['exact'] / m['source_rows'])} / {pct(m['exact_strict'] / m['source_rows'])}")
    rows.append(f"{d} & " + " & ".join(cells) + " \\\\")
wr("tab_migration", resize("\\begin{tabular}{lcccc}\n\\toprule\nDataset & No graph & Name-only graph & Proposed graph & Ground-truth plan \\\\\n\\midrule\n"
                           + "\n".join(rows) + "\n\\bottomrule\n\\end{tabular}\n"))

# two-phase detail (proposed + ground-truth plan)
rows = []
for d in DS:
    for p, lbl in (("Graph: Proposed", "Proposed"), ("Oracle (true dependencies)", "Ground truth")):
        m = mig(d, p)
        rows.append(f"{d if lbl == 'Proposed' else ''} & {lbl} & {m['deferred_columns']:.1f} & {m['notnull_deferred_columns']:.0f} & "
                    f"{n0(m['initially_loaded'])} & {n0(m['phase2_failures'])} & {n0(m['exact'])} & {n0(m['altered'])} & {n0(m['missing'])} & {n0(m['exact_strict'])} \\\\")
wr("tab_twophase", resize("\\begin{tabular}{llrrrrrrrr}\n\\toprule\n & & Deferred & & Loaded & Phase-2 & \\multicolumn{3}{c}{Null-and-flag policy} & Strict \\\\\n\\cmidrule(lr){7-9}\nDataset & Plan & cols. & NOT NULL & (phase 1) & failures & Exact & Altered & Missing & exact \\\\\n\\midrule\n"
                          + "\n".join(rows) + "\n\\bottomrule\n\\end{tabular}\n"))

# validation
rows = []
for d in DS:
    v = val(d); cb = v["corruptions_by_dependency_status"]; cl = v["clean"]
    def gf(x): return f"{x['graph']:.1f}/{x['n']:.1f}" if d in SYN else f"{x['graph']:.0f}/{x['n']:.0f}"
    def af(x): return f"{x['audit']:.1f}/{x['n']:.1f}" if d in SYN else f"{x['audit']:.0f}/{x['n']:.0f}"
    fmt = (lambda x: f"{x:.1f}") if d in SYN else (lambda x: f"{x:.0f}")
    rows.append(f"{d} & {fmt(v['missing_detected_graph'])}/{fmt(v['injected_missing_rows'])} & {gf(cb['recovered'])} & {gf(cb['missed'])} & "
                f"{af({'audit': cb['recovered']['audit'] + cb['missed']['audit'] + cb['wrong_target']['audit'], 'n': v['injected_corruptions']})} & "
                f"{fmt(cl['orphan_rows_flagged_on_true_edges'])}/{fmt(cl['orphan_rows_true_edges_audit'])} & {fmt(cl['orphan_rows_flagged_on_wrong_edges'])} \\\\")
wr("tab_validation", resize("\\begin{tabular}{lcccccc}\n\\toprule\n & Missing rows & \\multicolumn{2}{c}{Corrupted refs (graph)} & Corrupted refs & Source orphans & False alarms \\\\\n"
                            "\\cmidrule(lr){3-4}\nDataset & (graph) & recovered dep. & missed dep. & (audit) & (graph/audit) & (rows) \\\\\n\\midrule\n"
                            + "\n".join(rows) + "\n\\bottomrule\n\\end{tabular}\n"))

# cycles & graph errors
rows = []
for d in DS:
    c = (R["public"][d] if d in R["public"] else R["synthetic"][d])["cycles"]; v = val(d)
    fmt = (lambda x: f"{x:.1f}") if d in SYN else (lambda x: f"{x:.0f}")
    rows.append(f"{d} & {fmt(c['true_cyclic_columns'])} & {fmt(c['true_cyclic_columns_recovered'])} & {fmt(c['recovered_cyclic_columns'])} & "
                f"{fmt(v['wrong_edges'])} & {fmt(v['clean']['wrong_edges_raising_alerts'])} & {fmt(v['missed_dependencies'])} \\\\")
wr("tab_graph_errors", resize("\\begin{tabular}{lcccccc}\n\\toprule\n & \\multicolumn{3}{c}{Cyclic reference columns} & \\multicolumn{2}{c}{Wrong edges} & Missed \\\\\n"
                              "\\cmidrule(lr){2-4}\\cmidrule(lr){5-6}\nDataset & true & recovered & deferred & total & alerting & deps. \\\\\n\\midrule\n"
                              + "\n".join(rows) + "\n\\bottomrule\n\\end{tabular}\n"))

# sampling
SM = R["public"]["TPC-DS"]["sampling"]
rows = [f"{k if k != 'all' else 'all values'} & {f3(v['P'])} & {f3(v['R'])} & {f3(v['F1'])} & {v['secs']:.2f} \\\\" for k, v in SM.items()]
wr("tab_sampling", resize("\\begin{tabular}{lcccc}\n\\toprule\nSample size & Precision & Recall & F1 & Detection (s) \\\\\n\\midrule\n"
                          + "\n".join(rows) + "\n\\bottomrule\n\\end{tabular}\n"))

# stress
SM_ = RULES + ["Classifier (partial IND)", "Proposed + key inference"]
rows = []
for s, lbl in zip(snames, slabels):
    cells = []
    for m in SM_:
        dd = ST[s]["detection"].get(m)
        cells.append(f"{dd['F1']['mean']:.3f}" if dd else "--")
    rows.append(lbl.replace("\n", " ").replace("%", "\\%") + " & " + " & ".join(cells) + " \\\\")   # escape % for LaTeX
wr("tab_stress", resize("\\begin{tabular}{lcccccc}\n\\toprule\nCondition & Name-only & Data-only & Fixed fusion & Proposed & Classifier (partial) & Proposed + key inf. \\\\\n\\midrule\n"
                        + "\n".join(rows) + "\n\\bottomrule\n\\end{tabular}\n"))

# scalability
rows = []
for s in SC:
    dt = s["detect_s"]
    rows.append(f"{s['tables']:,} & {s['columns']:,} & {s['true_deps']:,} & {n0(s['type_compatible_pairs'])} & {n0(s['candidates_after_blocking'])} & "
                f"{dt['median']:.2f} [{dt['min']:.2f}--{dt['max']:.2f}] & {s['plan_s']['median']:.3f} & {f3(s['F1'])} & {s['speedup4_model']:.2f} & {s['speedup8_model']:.2f} \\\\")
wr("tab_scale", resize("\\begin{tabular}{rrrrrcccrr}\n\\toprule\n & & & & & & & & \\multicolumn{2}{c}{Modeled speedup} \\\\\n\\cmidrule(lr){9-10}\nTables & Columns & Deps. & Pairs & Candidates & Detect (s) & Plan (s) & F1 & 4 workers & 8 workers \\\\\n\\midrule\n"
                       + "\n".join(rows) + "\n\\bottomrule\n\\end{tabular}\n"))

# migration-critical dependencies (results/critical.json, from src/critical.py)
CR = json.load(open(os.path.join(ROOT, "results", "critical.json")))
def crit(d, g):
    return CR["public"][d][g] if d in CR["public"] else CR["synthetic"][d][g]
rows = []
for d in DS:
    for g, lbl in (("Graph: Name-only", "Name-only"), ("Graph: Proposed", "Proposed")):
        c, m = crit(d, g), mig(d, g)
        num = (lambda x: f"{x:.1f}") if d in SYN else (lambda x: f"{x:.0f}")
        rows.append(f"{d if lbl == 'Name-only' else ''} & {num(c['true']) if lbl == 'Name-only' else ''} & {lbl} & "
                    f"{num(c['missed'])} & {num(c['critical'])} & {pct(m['exact'] / m['source_rows'])} \\\\")
wr("tab_critical", resize("\\begin{tabular}{lrlrrr}\n\\toprule\n & True & & Missed & Migration-critical & Exact \\\\\nDataset & deps. & Graph & deps. & misses & migration \\\\\n\\midrule\n"
                          + "\n".join(rows) + "\n\\bottomrule\n\\end{tabular}\n"))

# ------------------------------------------------------------------ numbers for the text
E = R["environment"]; TP = R["public"]["TPC-DS"]; NW = R["public"]["Northwind"]
SL, SMo = R["synthetic"]["SynthLegacy-100"], R["synthetic"]["SynthModern-100"]
big = SC[-1]
def cmd(name, v): return f"\\newcommand{{\\{name}}}{{{v}}}\n"
nums = "".join([
    cmd("envCPU", E["cpu"].replace("(R)", "").replace("@", "at")), cmd("envCores", E["logical_cpus"]),
    cmd("envPython", E["python"]), cmd("reps", R["scalability"]["repetitions"]),
    cmd("tpcProposedFone", f3(det("TPC-DS", "Proposed (adaptive)"))), cmd("tpcNameFone", f3(det("TPC-DS", "Name-only"))),
    cmd("tpcDataFone", f3(det("TPC-DS", "Data-only (IND)"))), cmd("tpcFixedFone", f3(det("TPC-DS", "Fixed-weight fusion"))),
    cmd("tpcProposedP", f3(det("TPC-DS", "Proposed (adaptive)", "P"))), cmd("tpcProposedR", f3(det("TPC-DS", "Proposed (adaptive)", "R"))),
    cmd("tpcFixedP", f3(det("TPC-DS", "Fixed-weight fusion", "P"))),
    cmd("tpcClfExactFone", f3(det("TPC-DS", "Classifier (exact IND)"))), cmd("tpcClfPartialFone", f3(det("TPC-DS", "Classifier (partial IND)"))),
    cmd("tpcProposedTP", TP["detection"]["Proposed (adaptive)"]["TP"]), cmd("tpcNameTP", TP["detection"]["Name-only"]["TP"]),
    cmd("tpcProposedFP", TP["detection"]["Proposed (adaptive)"]["FP"]), cmd("tpcProposedFN", TP["detection"]["Proposed (adaptive)"]["FN"]),
    cmd("tpcRows", n0(TP["rows"])), cmd("tpcPairs", n0(TP["type_compatible_pairs"])), cmd("tpcCands", n0(TP["candidates_after_blocking"])),
    cmd("tpcDetected", TP["proposed_detected"]),
    cmd("tpcExactProposed", pct(mig("TPC-DS", "Graph: Proposed")["exact"] / mig("TPC-DS", "Graph: Proposed")["source_rows"])),
    cmd("tpcExactName", pct(mig("TPC-DS", "Graph: Name-only")["exact"] / mig("TPC-DS", "Graph: Name-only")["source_rows"])),
    cmd("tpcExactNone", pct(mig("TPC-DS", "No graph (alphabetical)")["exact"] / mig("TPC-DS", "No graph (alphabetical)")["source_rows"])),
    cmd("tpcProfileS", f"{TP['profile_s']:.1f}"),
    cmd("legProposedFone", f3(det("SynthLegacy-100", "Proposed (adaptive)"))), cmd("legProposedFoneSD", f3(sd("SynthLegacy-100", "Proposed (adaptive)"))),
    cmd("legNameFone", f3(det("SynthLegacy-100", "Name-only"))), cmd("legDataFone", f3(det("SynthLegacy-100", "Data-only (IND)"))),
    cmd("legFixedFone", f3(det("SynthLegacy-100", "Fixed-weight fusion"))),
    cmd("legClfPartialFone", f3(det("SynthLegacy-100", "Classifier (partial IND)"))), cmd("legClfExactFone", f3(det("SynthLegacy-100", "Classifier (exact IND)"))),
    cmd("modProposedFone", f3(det("SynthModern-100", "Proposed (adaptive)"))), cmd("modFixedFone", f3(det("SynthModern-100", "Fixed-weight fusion"))),
    cmd("modProposedFP", f"{SMo['detection']['Proposed (adaptive)']['FP']['mean']:.1f}"),
    cmd("modFixedFP", f"{SMo['detection']['Fixed-weight fusion']['FP']['mean']:.1f}"),
    cmd("legExactProposed", pct(mig("SynthLegacy-100", "Graph: Proposed")["exact"] / mig("SynthLegacy-100", "Graph: Proposed")["source_rows"])),
    cmd("legExactName", pct(mig("SynthLegacy-100", "Graph: Name-only")["exact"] / mig("SynthLegacy-100", "Graph: Name-only")["source_rows"])),
    cmd("legExactOracle", pct(mig("SynthLegacy-100", "Oracle (true dependencies)")["exact"] / mig("SynthLegacy-100", "Oracle (true dependencies)")["source_rows"])),
    cmd("legAlteredProposed", f"{mig('SynthLegacy-100', 'Graph: Proposed')['altered']:.1f}"),
    cmd("legAlteredOracle", f"{mig('SynthLegacy-100', 'Oracle (true dependencies)')['altered']:.1f}"),
    cmd("nwLostRows", n0(mig("Northwind", "Graph: Proposed")["missing"])),
    cmd("nwLostPct", pct(mig("Northwind", "Graph: Proposed")["missing"] / mig("Northwind", "Graph: Proposed")["source_rows"])),
    cmd("opaqueProposed", f"{100 * rb['Proposed (adaptive)']['opaque']:.0f}\\%"), cmd("opaqueFixed", f"{100 * rb['Fixed-weight fusion']['opaque']:.0f}\\%"),
    cmd("abbrevName", f"{100 * rb['Name-only']['abbrev']:.0f}\\%"), cmd("abbrevFixed", f"{100 * rb['Fixed-weight fusion']['abbrev']:.0f}\\%"),
    cmd("scaleMaxTables", f"{big['tables']:,}"), cmd("scaleMaxCols", f"{big['columns']:,}"),
    cmd("scaleMaxDetect", f"{big['detect_s']['median']:.1f}"), cmd("scaleMinDetect", f"{SC[0]['detect_s']['median']:.2f}"),
    cmd("scaleMaxSpeedFour", f"{big['speedup4_model']:.2f}"), cmd("scaleMaxSpeedEight", f"{big['speedup8_model']:.2f}"),
    cmd("scaleMaxPairs", n0(big["type_compatible_pairs"])), cmd("scaleMaxCands", n0(big["candidates_after_blocking"])),
    cmd("scaleMaxMinutes", f"{big['detect_s']['max'] / 60:.1f}"),
])

# --- validation, ablation, sampling, stress, semantic review
def v_(d): return val(d)["corruptions_by_dependency_status"]
VT, VL = val("TPC-DS"), val("SynthLegacy-100")
# Author's semantic review of TPC-DS detections that are absent from tpcds_ri.sql:
# columns whose values are valid keys of the referenced table and whose definition is a
# reference (dates as date keys, a customer key). See the paper's discussion section.
PLAUSIBLE = {("customer", "c_last_review_date_sk"), ("date_dim", "d_first_dom"), ("date_dim", "d_last_dom"),
             ("date_dim", "d_same_day_ly"), ("date_dim", "d_same_day_lq"), ("web_page", "wp_customer_sk")}
fps = [tuple(x) for x in TP["fp_by_proposed"]]
n_pl = sum(1 for x in fps if (x[0], x[1]) in PLAUSIBLE)
tpd = TP["detection"]["Proposed (adaptive)"]
sm = TP["sampling"]
STc = ST["Combined"]["detection"]; STn = ST["Missing primary keys (20% of tables)"]["detection"]
STcomp = ST["Composite keys (15 composite parents)"]["detection"]; STd = ST["Dirty references (25% orphans)"]["detection"]
nums += "".join([
    cmd("valTPCrecN", f"{v_('TPC-DS')['recovered']['n']:.0f}"), cmd("valTPCrecG", f"{v_('TPC-DS')['recovered']['graph']:.0f}"),
    cmd("valTPCmisN", f"{v_('TPC-DS')['missed']['n']:.0f}"), cmd("valTPCmisG", f"{v_('TPC-DS')['missed']['graph']:.0f}"),
    cmd("valTPCfalse", f"{VT['clean']['orphan_rows_flagged_on_wrong_edges']:,.0f}"),
    cmd("valTPCfalseEdges", f"{VT['clean']['wrong_edges_raising_alerts']:.0f}"),
    cmd("valLegrecN", f"{v_('SynthLegacy-100')['recovered']['n']:.1f}"), cmd("valLegrecG", f"{v_('SynthLegacy-100')['recovered']['graph']:.1f}"),
    cmd("valLegmisN", f"{v_('SynthLegacy-100')['missed']['n']:.1f}"), cmd("valLegmisG", f"{v_('SynthLegacy-100')['missed']['graph']:.1f}"),
    cmd("valLegSrcG", f"{VL['clean']['orphan_rows_flagged_on_true_edges']:.1f}"), cmd("valLegSrcA", f"{VL['clean']['orphan_rows_true_edges_audit']:.1f}"),
    cmd("valLegFalse", f"{VL['clean']['orphan_rows_flagged_on_wrong_edges']:.1f}"),
    cmd("ablTPCnoAdapt", f3(det("TPC-DS", "Proposed without adaptive rule"))), cmd("ablTPCnoSpec", f3(det("TPC-DS", "Proposed without specificity"))),
    cmd("ablSakilaNoSpec", f3(det("Sakila", "Proposed without specificity"))),
    cmd("ablLegNoAdapt", f3(det("SynthLegacy-100", "Proposed without adaptive rule"))), cmd("ablLegNoSpec", f3(det("SynthLegacy-100", "Proposed without specificity"))),
    cmd("sampSmallFone", f3(sm["100"]["F1"])), cmd("sampDefaultFone", f3(sm["1000"]["F1"])), cmd("sampAllFone", f3(sm["all"]["F1"])),
    cmd("sampDefaultS", f"{sm['1000']['secs']:.2f}"), cmd("sampAllS", f"{sm['all']['secs']:.2f}"),
    cmd("tpcPlausible", n_pl), cmd("tpcImplausible", len(fps) - n_pl),
    cmd("tpcSemPrec", f3((tpd["TP"] + n_pl) / (tpd["TP"] + tpd["FP"]))),
    cmd("stCombProp", f"{STc['Proposed (adaptive)']['F1']['mean']:.3f}"), cmd("stCombName", f"{STc['Name-only']['F1']['mean']:.3f}"),
    cmd("stCombData", f"{STc['Data-only (IND)']['F1']['mean']:.3f}"), cmd("stCombKI", f"{STc['Proposed + key inference']['F1']['mean']:.3f}"),
    cmd("stCombClf", f"{STc['Classifier (partial IND)']['F1']['mean']:.3f}"),
    cmd("stNoPkProp", f"{STn['Proposed (adaptive)']['F1']['mean']:.3f}"), cmd("stNoPkKI", f"{STn['Proposed + key inference']['F1']['mean']:.3f}"),
    cmd("stNoPkPropR", f"{STn['Proposed (adaptive)']['R']['mean']:.3f}"), cmd("stNoPkKIR", f"{STn['Proposed + key inference']['R']['mean']:.3f}"),
    cmd("stCompFPprop", f"{STcomp['Proposed (adaptive)']['FP_on_composite_columns']['mean']:.1f}"),
    cmd("stCompFPdata", f"{STcomp['Data-only (IND)']['FP_on_composite_columns']['mean']:.1f}"),
    cmd("stDirtyProp", f"{STd['Proposed (adaptive)']['F1']['mean']:.3f}"), cmd("stDirtyData", f"{STd['Data-only (IND)']['F1']['mean']:.3f}"),
    cmd("stBaseProp", f"{ST['Baseline (new seeds)']['detection']['Proposed (adaptive)']['F1']['mean']:.3f}"),
    cmd("stCompDeps", f"{ST['Composite keys (15 composite parents)']['ground_truth']['composite_deps']:.0f}"),
    cmd("stCompFPclf", f"{STcomp['Classifier (partial IND)']['FP_on_composite_columns']['mean']:.1f}"),
    cmd("stCompProp", f"{STcomp['Proposed (adaptive)']['F1']['mean']:.3f}"),
    cmd("stDirtyName", f"{STd['Name-only']['F1']['mean']:.3f}"), cmd("stDirtyFixed", f"{STd['Fixed-weight fusion']['F1']['mean']:.3f}"),
    cmd("stDirtyTenProp", f"{ST['Dirty references (10% orphans)']['detection']['Proposed (adaptive)']['F1']['mean']:.3f}"),
    cmd("stDirtyTenFixed", f"{ST['Dirty references (10% orphans)']['detection']['Fixed-weight fusion']['F1']['mean']:.3f}"),
    cmd("stNullProp", f"{ST['Sparse references (30% NULL)']['detection']['Proposed (adaptive)']['F1']['mean']:.3f}"),
    cmd("stAmbProp", f"{ST['Ambiguous keys (all integer)']['detection']['Proposed (adaptive)']['F1']['mean']:.3f}"),
    cmd("stAmbFixed", f"{ST['Ambiguous keys (all integer)']['detection']['Fixed-weight fusion']['F1']['mean']:.3f}"),
    cmd("stAmbPropP", f"{ST['Ambiguous keys (all integer)']['detection']['Proposed (adaptive)']['P']['mean']:.3f}"),
    cmd("stAmbData", f"{ST['Ambiguous keys (all integer)']['detection']['Data-only (IND)']['F1']['mean']:.3f}"),
    cmd("stCombFixed", f"{STc['Fixed-weight fusion']['F1']['mean']:.3f}"),
    cmd("stNoPkFixed", f"{STn['Fixed-weight fusion']['F1']['mean']:.3f}"),
    cmd("stNoPkDeps", f"{ST['Missing primary keys (20% of tables)']['ground_truth']['deps_to_undeclared_pk']:.1f}"),
    cmd("ablNWnoAdapt", f3(det("Northwind", "Proposed without adaptive rule"))),
    cmd("ablModNoAdapt", f3(det("SynthModern-100", "Proposed without adaptive rule"))),
    cmd("ablChinookNoSpec", f3(det("Chinook", "Proposed without specificity"))),
    cmd("ablNWNoSpec", f3(det("Northwind", "Proposed without specificity"))),
    cmd("legStrictProposed", pct(mig("SynthLegacy-100", "Graph: Proposed")["exact_strict"] / mig("SynthLegacy-100", "Graph: Proposed")["source_rows"])),
    cmd("legStrictOracle", pct(mig("SynthLegacy-100", "Oracle (true dependencies)")["exact_strict"] / mig("SynthLegacy-100", "Oracle (true dependencies)")["source_rows"])),
    cmd("modExactProposed", pct(mig("SynthModern-100", "Graph: Proposed")["exact"] / mig("SynthModern-100", "Graph: Proposed")["source_rows"])),
    cmd("modExactOracle", pct(mig("SynthModern-100", "Oracle (true dependencies)")["exact"] / mig("SynthModern-100", "Oracle (true dependencies)")["source_rows"])),
    cmd("modStrictProposed", pct(mig("SynthModern-100", "Graph: Proposed")["exact_strict"] / mig("SynthModern-100", "Graph: Proposed")["source_rows"])),
    cmd("modStrictOracle", pct(mig("SynthModern-100", "Oracle (true dependencies)")["exact_strict"] / mig("SynthModern-100", "Oracle (true dependencies)")["source_rows"])),
    cmd("valLegWrongN", f"{v_('SynthLegacy-100')['wrong_target']['n']:.1f}"), cmd("valLegWrongG", f"{v_('SynthLegacy-100')['wrong_target']['graph']:.1f}"),
    cmd("tpcPairsCands", f"{100 * TP['candidates_after_blocking'] / TP['type_compatible_pairs']:.0f}\\%"),
    cmd("scaleBlockShare", f"{100 * big['candidates_after_blocking'] / big['type_compatible_pairs']:.0f}\\%"),
    cmd("scaleMaxDetectMin", f"{big['detect_s']['min']:.1f}"), cmd("scaleMaxDetectMax", f"{big['detect_s']['max']:.1f}"),
    cmd("modClfPartialFone", f3(det("SynthModern-100", "Classifier (partial IND)"))),
    cmd("legClfExactFoneB", f3(det("SynthLegacy-100", "Classifier (exact IND)"))),
    cmd("modClfExactFone", f3(det("SynthModern-100", "Classifier (exact IND)"))),
    cmd("sampSmallS", f"{sm['100']['secs']:.2f}"),
    cmd("tpcMissedName", f"{crit('TPC-DS', 'Graph: Name-only')['missed']:.0f}"),
    cmd("tpcCritName", f"{crit('TPC-DS', 'Graph: Name-only')['critical']:.0f}"),
    cmd("tpcCritProposed", f"{crit('TPC-DS', 'Graph: Proposed')['critical']:.0f}"),
    cmd("legMissedProposed", f"{crit('SynthLegacy-100', 'Graph: Proposed')['missed']:.1f}"),
    cmd("legCritProposed", f"{crit('SynthLegacy-100', 'Graph: Proposed')['critical']:.1f}"),
    cmd("legMissedName", f"{crit('SynthLegacy-100', 'Graph: Name-only')['missed']:.1f}"),
    cmd("legCritName", f"{crit('SynthLegacy-100', 'Graph: Name-only')['critical']:.1f}"),
    cmd("chCritProposed", f"{crit('Chinook', 'Graph: Proposed')['critical']:.0f}"),
    cmd("chExactProposed", pct(mig('Chinook', 'Graph: Proposed')['exact'] / mig('Chinook', 'Graph: Proposed')['source_rows'])),
])
open(os.path.join(TEX, "numbers.tex"), "w").write(nums)

# TPC-DS detections absent from the ground truth, with the semantic review
rows = [f"\\texttt{{{a}.{b}}} & \\texttt{{{c}.{d}}} & {'plausible reference' if (a, b) in PLAUSIBLE else 'coincidental'} \\\\"
        .replace("_", "\\_") for a, b, c, d in fps]
wr("tab_tpcds_fp", resize("\\begin{tabular}{llc}\n\\toprule\nColumn & Detected target & Review \\\\\n\\midrule\n"
                          + "\n".join(rows) + "\n\\bottomrule\n\\end{tabular}\n"))

# ------------------------------------------------------------------ markdown mirror
L = [f"# Results tables\n\nGenerated from results/results.json. Environment: {E['cpu']}, {E['logical_cpus']} logical CPUs, "
     f"Python {E['python']}, NetworkX {E['networkx']}, scikit-learn {E['scikit_learn']}, SQLite {E['sqlite']}.\n"]
L += ["## Detection (all declared constraints hidden)\n", "| Dataset | Method | Precision | Recall | F1 |", "|---|---|---|---|---|"]
for d in DS:
    for m in RULES + CLFS + ABL[1:]:
        if d in R["public"]:
            L.append(f"| {d} | {m} | {det(d, m, 'P'):.3f} | {det(d, m, 'R'):.3f} | {det(d, m):.3f} |")
        else:
            L.append(f"| {d} | {m} | {det(d, m, 'P'):.3f} ± {sd(d, m, 'P'):.3f} | {det(d, m, 'R'):.3f} ± {sd(d, m, 'R'):.3f} | {det(d, m):.3f} ± {sd(d, m):.3f} |")
L += ["\n## Migration: initially loaded / exact (null-and-flag) / exact (strict) (share of source rows)\n", "| Dataset | " + " | ".join(PLAN_LBL) + " |", "|---|---|---|---|---|"]
for d in DS:
    L.append(f"| {d} | " + " | ".join(f"{100 * mig(d, p)['initially_loaded'] / mig(d, p)['source_rows']:.1f}% / {100 * mig(d, p)['exact'] / mig(d, p)['source_rows']:.1f}% / {100 * mig(d, p)['exact_strict'] / mig(d, p)['source_rows']:.1f}%" for p in PLANS) + " |")
L += ["\n## Validation (proposed graph, 50 deleted rows + 50 corrupted references injected)\n",
      "| Dataset | Missing rows found (graph) | Corruptions found on recovered deps (graph) | on missed deps (graph) | Corruptions found (audit) | False-alarm rows |", "|---|---|---|---|---|---|"]
for d in DS:
    v = val(d); cb = v["corruptions_by_dependency_status"]
    L.append(f"| {d} | {v['missing_detected_graph']:.1f}/{v['injected_missing_rows']:.0f} | {cb['recovered']['graph']:.1f}/{cb['recovered']['n']:.1f} | "
             f"{cb['missed']['graph']:.1f}/{cb['missed']['n']:.1f} | {v['corruptions_detected_audit']:.1f}/{v['injected_corruptions']:.0f} | {v['clean']['orphan_rows_flagged_on_wrong_edges']:.1f} |")
L += ["\n## Stress test (SynthLegacy profile, seeds 301-305, F1)\n", "| Condition | " + " | ".join(SM_) + " |", "|---|" + "---|" * len(SM_)]
for s in snames:
    L.append(f"| {s} | " + " | ".join(f"{ST[s]['detection'][m]['F1']['mean']:.3f}" if m in ST[s]["detection"] else "--" for m in SM_) + " |")
L += ["\n## Scalability (SynthLegacy, proposed method)\n", "| Tables | Columns | Detect median [min-max] (s) | F1 |", "|---|---|---|---|"]
for s in SC:
    L.append(f"| {s['tables']} | {s['columns']} | {s['detect_s']['median']:.2f} [{s['detect_s']['min']:.2f}-{s['detect_s']['max']:.2f}] | {s['F1']:.3f} |")
open(os.path.join(ROOT, "results", "tables.md"), "w").write("\n".join(L) + "\n")
print("figures, LaTeX tables and numbers written to results/")
