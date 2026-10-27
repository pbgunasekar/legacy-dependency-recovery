"""Runs every experiment reported in the paper and writes ONE results file,
results/results.json, including the hardware and software it ran on. Every number,
table and figure in the paper is derived from this file by make_figures.py.

Protocol
- Parameters are tuned on development seeds 101-103 only (src/tune.py) and frozen in
  params.json. Test seeds 201-205. Public datasets are never used for tuning.
- The stress test (seeds 301-305) and the classifier baseline were added in revision 1,
  after the method and its parameters were frozen; the method was not changed afterwards.

Experiments
  E1 detection accuracy (public + synthetic), incl. classifier baselines and ablations
  E2 recall by naming style
  E3 migration: initial load vs final state (exact / altered / missing rows)
  E4 validation: graph-based validation vs independent audit, with fault injection
  E5 scalability (3 repetitions, median)          E6 sensitivity to alpha
  E7 sampling sensitivity                         E8 stress test
"""
import sys, os, json, time, platform, random, statistics as st, sqlite3
sys.path.insert(0, os.path.dirname(__file__))
import networkx, sklearn
import kgmig as K, synth as S, baselines as B

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = json.load(open(os.path.join(ROOT, "params.json")))
CONF = dict(method="confidence", alpha=P["confidence"]["alpha"], tau=P["confidence"]["tau"],
            min_inc=P["confidence"]["min_inc"])
DATA = dict(method="data", tau=P["data"]["tau"], min_inc=P["data"]["min_inc"])
NAME = dict(method="name")
A = P["adaptive"]
ADAPT = dict(method="confidence", alpha=A["alpha"], tau=A["tau"], min_inc=A["min_inc"],
             adaptive=True, h0=A["h0"], strict_inc=A["strict_inc"])
RULE_METHODS = {"Name-only": NAME, "Data-only (IND)": DATA, "Fixed-weight fusion": CONF,
                "Proposed (adaptive)": ADAPT}
ABLATIONS = {"Proposed without adaptive rule": {**ADAPT, "adaptive": False},
             "Proposed without specificity": {**ADAPT, "use_spec": False}}
PROP = "Proposed (adaptive)"
PUBLIC = {"Chinook": "chinook.db", "Northwind": "northwind.db", "Sakila": "sakila.db",
          "TPC-DS": "tpcds_sf1.db"}
SYNTH = {"SynthModern-100": "modern", "SynthLegacy-100": "legacy"}
TEST_SEEDS = [201, 202, 203, 204, 205]
STRESS_SEEDS = [301, 302, 303, 304, 305]
GATE = A["min_inc"]

def environment():
    cpu = "unknown"
    try:
        for line in open("/proc/cpuinfo"):
            if line.startswith("model name"):
                cpu = line.split(":", 1)[1].strip(); break
    except OSError:
        cpu = platform.processor() or "unknown"
    return {"cpu": cpu, "logical_cpus": os.cpu_count(), "os": platform.platform(),
            "python": platform.python_version(), "networkx": networkx.__version__,
            "scikit_learn": sklearn.__version__, "sqlite": sqlite3.sqlite_version,
            "started": time.strftime("%Y-%m-%d %H:%M:%S %Z")}

out = {"environment": environment(), "params": P}
missing = [f for f in PUBLIC.values() if not os.path.exists(os.path.join(ROOT, "schemas", f))]
if missing:
    sys.exit(f"Missing {missing}: run src/fetch_data.py and src/build_tpcds.py first.")

# ------------------------------------------------ classifier baseline (dev seeds only)
dev = []
for prof in ["modern", "legacy"]:
    for seed in [101, 102, 103]:
        c, T = S.generate(":memory:", 60, prof, seed)
        dev.append((K.standardize(K.extract(c)), T)); c.close()
CLF = {mode: B.train(dev, mode, GATE) for mode in ("exact", "partial")}
del dev

def _prf(d, T, dt):
    Pp, R, F, tp, fp, fn = K.prf(d, T)
    return {"P": Pp, "R": R, "F1": F, "TP": tp, "FP": fp, "FN": fn, "secs": dt}

def run_methods(md, T):
    rows, deps = {}, {}
    for m, kw in {**RULE_METHODS, **ABLATIONS}.items():
        t0 = time.perf_counter(); d = K.detect(md, **kw); dt = time.perf_counter() - t0
        rows[m], deps[m] = _prf(d, T, dt), d
    for mode, label in (("exact", "Classifier (exact IND)"), ("partial", "Classifier (partial IND)")):
        t0 = time.perf_counter(); d = B.detect_classifier(md, CLF[mode], mode, GATE); dt = time.perf_counter() - t0
        rows[label], deps[label] = _prf(d, T, dt), d
    return rows, deps

# ------------------------------------------------------------------ E3 migration
def migration(conn, md, T, deps):
    plans = {"No graph (alphabetical)": K.naive_plan(md),
             "Graph: Name-only": K.plan(md, deps["Name-only"]),
             "Graph: Proposed": K.plan(md, deps[PROP]),
             "Oracle (true dependencies)": K.plan(md, {e: 1 for e in T})}
    res = {}
    for name, pl in plans.items():
        tgt, stt = K.migrate(conn, md, pl, T)
        fs = K.final_state(conn, tgt, md)
        res[name] = {"source_rows": stt["loaded"] + stt["rejected"],
                     "initially_loaded": stt["loaded"], "rejected": stt["rejected"],
                     "deferred_columns": len(pl["deferred"]),
                     "notnull_deferred_columns": sum(1 for (t, c, k) in pl["deferred"] if md["tables"][t]["notnull"][c]),
                     "phase2_failures": stt["patch_fail"], **fs,
                     "Sq": K.ordering_score(pl["order"], T), "waves": len(pl["waves"]),
                     "cycles": len(pl["cycles"]),
                     "speedup4_model": K.parallel_speedup(md, pl, 4) if name != "No graph (alphabetical)" else 1.0}
        tgt.close()
    return res

# ------------------------------------------------------------------ E4 validation
def validation(conn, md, T, deps, seed, n_missing=50, n_corrupt=50):
    """Unenforced load with the proposed plan, then (a) checks on the clean target and
    (b) fault injection: deleted rows and corrupted references along TRUE dependencies.
    Compares graph-based validation (recovered dependencies) with an independent audit."""
    pl = K.plan(md, deps)
    tgt = K.load_unenforced(conn, md, pl["order"])
    for t, ti in md["tables"].items():
        if ti["pk"]:
            tgt.execute(f'create index "ix_{t}" on "{t}" ({",".join(chr(34)+p+chr(34) for p in ti["pk"])})')
    recovered, fp_edges = set(deps), set(deps) - T
    # (a) clean target
    miss0, flag0 = K.graph_validate(conn, tgt, md, deps)
    _, aorph0 = K.audit(conn, tgt, md, T)
    clean = {"missing_rows_flagged": sum(len(v) for v in miss0.values()),
             "orphan_rows_true_edges_audit": sum(len(v) for v in aorph0.values()),
             "orphan_rows_flagged_on_true_edges": sum(len(v) for e, v in flag0.items() if e in T),
             "orphan_rows_flagged_on_wrong_edges": sum(len(v) for e, v in flag0.items() if e not in T),
             "wrong_edges_raising_alerts": sum(1 for e, v in flag0.items() if e not in T and v)}
    # (b) fault injection on tables with a primary key
    rng = random.Random(seed)
    pk_tables = sorted(t for t, ti in md["tables"].items() if ti["pk"] and ti["rows"])
    deleted = set()
    while len(deleted) < n_missing:
        t = rng.choice(pk_tables); ti = md["tables"][t]
        kc = ",".join(f'"{p}"' for p in ti["pk"])
        row = tgt.execute(f'select {kc} from "{t}" order by {kc} limit 1 offset ?',
                          (rng.randrange(ti["rows"]),)).fetchone()
        if row is not None and (t, row) not in deleted:
            deleted.add((t, row))
            tgt.execute(f'delete from "{t}" where {" and ".join(chr(34)+p+chr(34)+"=?" for p in ti["pk"])}', row)
    true_on_pk = sorted(e for e in T if md["tables"][e[0]]["pk"])
    corrupted = []; tries = 0
    while len(corrupted) < n_corrupt and tries < 100 * n_corrupt:
        tries += 1
        t, c, pt, k = rng.choice(true_on_pk); ti = md["tables"][t]
        kc = ",".join(f'"{p}"' for p in ti["pk"])
        n = tgt.execute(f'select count(*) from "{t}" where "{c}" is not null').fetchone()[0]
        if not n:
            continue
        row = tgt.execute(f'select {kc} from "{t}" where "{c}" is not null order by {kc} limit 1 offset ?',
                          (rng.randrange(n),)).fetchone()
        if any(x[0] == t and row in (x[2], x[3]) for x in corrupted) or (t, row) in deleted:
            continue
        fam = md["tables"][t]["canon"][c]["family"]
        bad = 10**9 + len(corrupted) if fam == "num" else f"QQ{len(corrupted):08d}"
        tgt.execute(f'update "{t}" set "{c}"=? where {" and ".join(chr(34)+p+chr(34)+"=?" for p in ti["pk"])}',
                    (bad, *row))
        # if the reference column is part of the primary key, the row's key changes too
        new_row = tuple(bad if p == c else v for p, v in zip(ti["pk"], row))
        corrupted.append((t, c, row, new_row, (t, c, pt, k)))
    miss1, flag1 = K.graph_validate(conn, tgt, md, deps)
    diff1, _ = K.audit(conn, tgt, md, T)
    del_graph = sum(1 for t, row in deleted if row in miss1[t])
    audit_changed = {}
    for t, (lost, extra) in diff1.items():
        cols = md["tables"][t]["columns"]
        audit_changed[t] = {tuple(r[cols.index(p)] for p in md["tables"][t]["pk"])
                            for r in list(lost) + list(extra)} if md["tables"][t]["pk"] else set()
    del_audit = sum(1 for t, row in deleted if row in audit_changed[t])
    cats = {"recovered": [0, 0, 0], "wrong_target": [0, 0, 0], "missed": [0, 0, 0]}   # n, graph, audit
    rec_cols = {(e[0], e[1]) for e in recovered}
    for t, c, row, new_row, e in corrupted:
        cat = "recovered" if e in recovered else ("wrong_target" if (t, c) in rec_cols else "missed")
        hit = any(new_row in v for ed, v in flag1.items() if ed[0] == t and ed[1] == c)
        cats[cat][0] += 1; cats[cat][1] += hit
        cats[cat][2] += (row in audit_changed[t]) or (new_row in audit_changed[t])
    tgt.close()
    return {"clean": clean,
            "injected_missing_rows": len(deleted), "missing_detected_graph": del_graph,
            "missing_detected_audit": del_audit,
            "injected_corruptions": len(corrupted),
            "corruptions_detected_graph": sum(v[1] for v in cats.values()),
            "corruptions_detected_audit": sum(v[2] for v in cats.values()),
            "corruptions_by_dependency_status": {k: {"n": v[0], "graph": v[1], "audit": v[2]} for k, v in cats.items()},
            "true_dependencies": len(T), "recovered_true": len(recovered & T),
            "wrong_edges": len(fp_edges), "missed_dependencies": len(T - recovered)}

def cycle_info(md, T, deps):
    tp, pp = K.plan(md, {e: 1 for e in T}), K.plan(md, deps)
    true_cols = {(t, c) for (t, c, k) in tp["deferred"]}
    prop_cols = {(t, c) for (t, c, k) in pp["deferred"]}
    return {"true_cycles": len(tp["cycles"]), "true_cyclic_columns": len(true_cols),
            "recovered_cycles": len(pp["cycles"]), "recovered_cyclic_columns": len(prop_cols),
            "true_cyclic_columns_recovered": len(true_cols & prop_cols)}

def mean_sd(rows, keys):
    return {k: {"mean": st.mean(x[k] for x in rows), "sd": st.pstdev(x[k] for x in rows)} for k in keys}

def mean_nested(dicts):
    """Mean of numeric leaves across a list of identically shaped dicts."""
    if isinstance(dicts[0], dict):
        return {k: mean_nested([d[k] for d in dicts]) for k in dicts[0]}
    return st.mean(dicts)

# ================================================================ public datasets
out["public"] = {}
for nm, f in PUBLIC.items():
    conn = sqlite3.connect(os.path.join(ROOT, "schemas", f))
    t0 = time.perf_counter(); md = K.standardize(K.extract(conn)); prof_s = time.perf_counter() - t0
    T = md["fks"]
    tot, blk = K.candidate_counts(md)
    r = {"tables": len(md["tables"]), "columns": sum(len(t["columns"]) for t in md["tables"].values()),
         "rows": sum(t["rows"] for t in md["tables"].values()), "true_deps": len(T),
         "profile_s": prof_s, "type_compatible_pairs": tot, "candidates_after_blocking": blk}
    r["detection"], deps = run_methods(md, T)
    r["proposed_detected"] = len(deps[PROP])
    r["missed_by_proposed"] = sorted(map(list, T - set(deps[PROP])))
    r["fp_by_proposed"] = sorted(map(list, set(deps[PROP]) - T))
    r["migration"] = migration(conn, md, T, deps)
    r["validation"] = validation(conn, md, T, deps[PROP], seed=7)
    r["cycles"] = cycle_info(md, T, deps[PROP])
    D = K.table_graph(md, deps[PROP])
    imp = [len(K.impact(D, t)) / len(md["tables"]) for t in md["tables"]]
    r["impact"] = {"mean_Is": st.mean(imp), "max_Is": max(imp)}
    if nm == "TPC-DS":   # E7 sampling sensitivity on the dataset with large columns
        r["sampling"] = {}
        for smp in [100, 250, 1000, 5000, None]:
            t0 = time.perf_counter(); d = K.detect(md, **ADAPT, sample=smp); dt = time.perf_counter() - t0
            Pp, R, F, *_ = K.prf(d, T)
            r["sampling"][str(smp or "all")] = {"P": Pp, "R": R, "F1": F, "secs": dt}
    out["public"][nm] = r; conn.close()
    print(nm, {m: round(v["F1"], 3) for m, v in r["detection"].items()}, flush=True)

# ============================================================== synthetic datasets
os.makedirs(os.path.join(ROOT, "synth"), exist_ok=True)
out["synthetic"] = {}
alphas = [0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]
for dname, prof in SYNTH.items():
    agg, style_hits, mig, val, cyc, cand = {}, {}, [], [], [], []
    sens = {a: [] for a in alphas}
    for seed in TEST_SEEDS:
        p = os.path.join(ROOT, "synth", f"synth_{prof}_s{seed}.db")
        if os.path.exists(p): os.remove(p)
        conn, T = S.generate(p, 100, prof, seed); styles = dict(S.LAST_STYLES)
        md = K.standardize(K.extract(conn))
        cand.append(dict(zip(("type_compatible_pairs", "candidates_after_blocking"), K.candidate_counts(md))))
        rows, deps = run_methods(md, T)
        for m, row in rows.items():
            agg.setdefault(m, []).append(row)
            for e in T:
                s = styles[e]; style_hits.setdefault(m, {}).setdefault(s, [0, 0])
                style_hits[m][s][0] += e in deps[m]; style_hits[m][s][1] += 1
        for a in alphas:
            sens[a].append(K.prf(K.detect(md, **{**ADAPT, "alpha": a}), T)[2])
        mig.append(migration(conn, md, T, deps))
        val.append(validation(conn, md, T, deps[PROP], seed=seed))
        cyc.append(cycle_info(md, T, deps[PROP]))
        conn.close()
    out["synthetic"][dname] = {
        "detection": {m: mean_sd(rows, ("P", "R", "F1", "FP", "FN")) for m, rows in agg.items()},
        "recall_by_style": {m: {s: h / n for s, (h, n) in d.items()} for m, d in style_hits.items()},
        "style_counts": {s: n for s, (h, n) in style_hits["Name-only"].items()},
        "candidates": mean_nested(cand),
        "migration": mean_nested(mig), "validation": mean_nested(val), "cycles": mean_nested(cyc),
        "alpha_sensitivity": {str(a): st.mean(v) for a, v in sens.items()}}
    print(dname, {m: round(v["F1"]["mean"], 3) for m, v in out["synthetic"][dname]["detection"].items()}, flush=True)

# ================================================================== E8 stress test
STRESS = {
    "Baseline (new seeds)": {},
    "Dirty references (10% orphans)": {"orphan_rate": 0.10},
    "Dirty references (25% orphans)": {"orphan_rate": 0.25},
    "Sparse references (30% NULL)": {"null_rate": 0.30},
    "Ambiguous keys (all integer)": {"string_key_frac": 0.0},
    "Missing primary keys (20% of tables)": {"missing_pk_frac": 0.20},
    "Composite keys (15 composite parents)": {"composite_frac": 0.15},
    "Combined": {"orphan_rate": 0.10, "null_rate": 0.30, "string_key_frac": 0.0,
                 "missing_pk_frac": 0.20, "composite_frac": 0.15},
}
out["stress"] = {}
for sname, opts in STRESS.items():
    rows = {}; gt = []
    for seed in STRESS_SEEDS:
        conn, T = S.generate(":memory:", 100, "legacy", seed, **opts)
        no_pk, comp = set(S.LAST_NO_PK), set(S.LAST_COMPOSITE)
        comp_cols = {(t, c) for (t, cs, pt, ks) in comp for c in cs}
        md = K.standardize(K.extract(conn))
        T_in = {e for e in T if e[2] not in no_pk}
        variants = {m: K.detect(md, **kw) for m, kw in RULE_METHODS.items()}
        variants["Classifier (partial IND)"] = B.detect_classifier(md, CLF["partial"], "partial", GATE)
        if opts.get("missing_pk_frac"):
            K.infer_keys(md)
            variants["Proposed + key inference"] = K.detect(md, **ADAPT)
        for m, d in variants.items():
            Pp, R, F, tp, fp, fn = K.prf(d, T)
            rows.setdefault(m, []).append({"P": Pp, "R": R, "F1": F,
                                           "R_declared_parents": K.prf(d, T_in)[1] if T_in else 0.0,
                                           "FP_on_composite_columns": sum(1 for e in d if (e[0], e[1]) in comp_cols)})
        gt.append({"single_column_deps": len(T), "deps_to_undeclared_pk": len(T) - len(T_in),
                   "composite_deps": len(comp)})
        conn.close()
    out["stress"][sname] = {"options": opts,
                            "detection": {m: mean_sd(r, ("P", "R", "F1", "R_declared_parents", "FP_on_composite_columns"))
                                          for m, r in rows.items()},
                            "ground_truth": mean_nested(gt)}
    print("stress", sname, {m: round(v["F1"]["mean"], 3) for m, v in out["stress"][sname]["detection"].items()}, flush=True)

# ================================================================ E5 scalability
REPS = 3
out["scalability"] = {"repetitions": REPS, "rows": []}
for n in [50, 100, 250, 500, 1000, 2000]:
    p = os.path.join(ROOT, "synth", f"synth_legacy_scale{n}_s{900 + n}.db")
    if os.path.exists(p): os.remove(p)
    conn, T = S.generate(p, n, "legacy", 900 + n, rows=(20, 200))
    times = {k: [] for k in ("extract_s", "standardize_s", "detect_s", "graph_s", "plan_s")}
    for rep in range(REPS):
        t0 = time.perf_counter(); md = K.extract(conn); t1 = time.perf_counter()
        K.standardize(md); t2 = time.perf_counter()
        d = K.detect(md, **ADAPT); t3 = time.perf_counter()
        G = K.build_graph(md, d); t4 = time.perf_counter()
        pl = K.plan(md, d); t5 = time.perf_counter()
        for k, v in zip(times, (t1 - t0, t2 - t1, t3 - t2, t4 - t3, t5 - t4)):
            times[k].append(v)
    tot, blk = K.candidate_counts(md)
    row = {"tables": n, "columns": sum(len(t["columns"]) for t in md["tables"].values()),
           "rows": sum(t["rows"] for t in md["tables"].values()),
           "true_deps": len(T), "type_compatible_pairs": tot, "candidates_after_blocking": blk,
           "graph_nodes": G.number_of_nodes(), "graph_edges": G.number_of_edges(),
           "F1": K.prf(d, T)[2], "waves": len(pl["waves"]),
           "speedup4_model": K.parallel_speedup(md, pl, 4), "speedup8_model": K.parallel_speedup(md, pl, 8)}
    for k, v in times.items():
        row[k] = {"median": st.median(v), "min": min(v), "max": max(v), "all": v}
    out["scalability"]["rows"].append(row)
    print("scale", n, "detect median", round(row["detect_s"]["median"], 2), "s F1", round(row["F1"], 3), flush=True)
    conn.close(); os.remove(p)

out["environment"]["finished"] = time.strftime("%Y-%m-%d %H:%M:%S %Z")
os.makedirs(os.path.join(ROOT, "results"), exist_ok=True)
json.dump(out, open(os.environ.get("OUT", os.path.join(ROOT, "results", "results.json")), "w"),
          indent=1, default=list)
print("done")
