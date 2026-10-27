"""Runs all experiments; writes results/results.json. Parameters come from params.json
(tuned on dev seeds 101-103 only); test seeds are 201-205; public schemas are never tuned on."""
import sys, os, json, time, statistics as st, sqlite3
sys.path.insert(0, os.path.dirname(__file__))
import kgmig as K, synth as S

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = json.load(open(os.path.join(ROOT, "params.json")))
CONF = dict(method="confidence", alpha=P["confidence"]["alpha"], tau=P["confidence"]["tau"],
            min_inc=P["confidence"]["min_inc"])
DATA = dict(method="data", tau=P["data"]["tau"], min_inc=P["data"]["min_inc"])
NAME = dict(method="name")
A = P["adaptive"]
ADAPT = dict(method="confidence", alpha=A["alpha"], tau=A["tau"], min_inc=A["min_inc"],
             adaptive=True, h0=A["h0"], strict_inc=A["strict_inc"])
METHODS = {"Name-only": NAME, "Data-only (IND)": DATA, "Fixed-weight fusion": CONF,
           "Proposed (adaptive)": ADAPT}
PROP = "Proposed (adaptive)"
PUBLIC = {"Chinook": "chinook.db", "Northwind": "northwind.db", "Sakila": "sakila.db",
          "TPC-DS": "tpcds_sf1.db"}          # TPC-DS built by src/build_tpcds.py
SYNTH = {"SynthModern-100": "modern", "SynthLegacy-100": "legacy"}   # dataset name -> naming profile
TEST_SEEDS = [201, 202, 203, 204, 205]
out = {"params": P}

def det_row(md, T, kw):
    t0 = time.perf_counter(); d = K.detect(md, **kw); dt = time.perf_counter() - t0
    Pp, R, F, tp, fp, fn = K.prf(d, T)
    return {"P": Pp, "R": R, "F1": F, "TP": tp, "FP": fp, "FN": fn, "secs": dt}, d

def migration_rows(conn, md, T, deps_by_method):
    rows = {}
    plans = {"No graph (alphabetical)": K.naive_plan(md)}
    for m, d in deps_by_method.items():
        plans[f"Graph: {m}"] = K.plan(md, d)
    plans["Oracle (declared FKs)"] = K.plan(md, {e: 1 for e in T})
    for name, pl in plans.items():
        tgt, stt = K.migrate(conn, md, pl, T)
        rows[name] = {"Sq": K.ordering_score(pl["order"], T), "rejected": stt["rejected"],
                      "patch_fail": stt["patch_fail"], "loaded": stt["loaded"],
                      "waves": len(pl["waves"]), "cycles": len(pl["cycles"]),
                      "validation_Av": K.validate(conn, tgt, md, T),
                      "speedup4": K.parallel_speedup(md, pl, 4) if name != "No graph (alphabetical)" else 1.0}
    return rows

# ---------------- E1 / E3: public schemas
out["public"] = {}
for nm, f in PUBLIC.items():
    conn = sqlite3.connect(os.path.join(ROOT, "schemas", f))
    md = K.standardize(K.extract(conn)); T = md["fks"]
    r = {"tables": len(md["tables"]), "columns": sum(len(t["columns"]) for t in md["tables"].values()),
         "rows": sum(t["rows"] for t in md["tables"].values()), "true_deps": len(T), "detection": {}}
    deps = {}
    for m, kw in METHODS.items():
        r["detection"][m], deps[m] = det_row(md, T, kw)
    r["missed_by_proposed"] = sorted(map(list, T - set(deps[PROP])))
    r["fp_by_proposed"] = sorted(map(list, set(deps[PROP]) - T))
    r["migration"] = migration_rows(conn, md, T, {"Name-only": deps["Name-only"],
                                                   "Proposed": deps[PROP]})
    D = K.table_graph(md, deps[PROP])
    imp = [len(K.impact(D, t)) / len(md["tables"]) for t in md["tables"]]
    r["impact"] = {"mean_Is": st.mean(imp), "max_Is": max(imp)}
    out["public"][nm] = r
    print(nm, {m: round(v["F1"], 3) for m, v in r["detection"].items()})

# ---------------- E2 / E3: synthetic test schemas
os.makedirs(os.path.join(ROOT, "synth"), exist_ok=True)
out["synthetic"] = {}
alphas = [0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]
for dname, prof in SYNTH.items():
    agg = {m: [] for m in METHODS}; style_hits = {}; mig = []; sens = {a: [] for a in alphas}
    for seed in TEST_SEEDS:
        p = os.path.join(ROOT, "synth", f"synth_{prof}_s{seed}.db")
        if os.path.exists(p): os.remove(p)
        conn, T = S.generate(p, 100, prof, seed); styles = dict(S.LAST_STYLES)
        md = K.standardize(K.extract(conn))
        deps = {}
        for m, kw in METHODS.items():
            row, deps[m] = det_row(md, T, kw); agg[m].append(row)
            for e in T:
                s = styles[e]; style_hits.setdefault(m, {}).setdefault(s, [0, 0])
                style_hits[m][s][0] += e in deps[m]; style_hits[m][s][1] += 1
        for a in alphas:   # sensitivity: alpha sweep at tuned tau / gate
            sens[a].append(K.prf(K.detect(md, **{**ADAPT, "alpha": a}), T)[2])
        mig.append(migration_rows(conn, md, T, {"Name-only": deps["Name-only"],
                                                "Proposed": deps[PROP]}))
        conn.close()
    summ = {}
    for m, rows in agg.items():
        summ[m] = {k: {"mean": st.mean(r[k] for r in rows), "sd": st.pstdev(r[k] for r in rows)}
                   for k in ("P", "R", "F1", "FP", "FN")}
    migsum = {}
    for plan_name in mig[0]:
        migsum[plan_name] = {k: st.mean(m[plan_name][k] for m in mig) for k in mig[0][plan_name]}
    out["synthetic"][dname] = {"detection": summ,
                              "recall_by_style": {m: {s: h / n for s, (h, n) in d.items()} for m, d in style_hits.items()},
                              "style_counts": {s: n for s, (h, n) in style_hits["Name-only"].items()},
                              "migration": migsum,
                              "alpha_sensitivity": {str(a): st.mean(v) for a, v in sens.items()}}
    print(dname, {m: round(v["F1"]["mean"], 3) for m, v in summ.items()})

# ---------------- E5: scalability (SynthLegacy, 50-2000 tables)
out["scalability"] = []
for n in [50, 100, 250, 500, 1000, 2000]:
    p = os.path.join(ROOT, "synth", f"synth_legacy_scale{n}_s{900 + n}.db")
    if os.path.exists(p): os.remove(p)
    conn, T = S.generate(p, n, "legacy", 900 + n, rows=(20, 200))
    t0 = time.perf_counter(); md = K.extract(conn); t1 = time.perf_counter()
    K.standardize(md); t2 = time.perf_counter()
    d = K.detect(md, **ADAPT); t3 = time.perf_counter()
    G = K.build_graph(md, d); t4 = time.perf_counter()
    pl = K.plan(md, d); t5 = time.perf_counter()
    D = K.table_graph(md, d); _ = [K.impact(D, t) for t in list(md["tables"])[:100]]; t6 = time.perf_counter()
    row = {"tables": n, "columns": sum(len(t["columns"]) for t in md["tables"].values()),
           "true_deps": len(T), "graph_nodes": G.number_of_nodes(), "graph_edges": G.number_of_edges(),
           "extract_s": t1 - t0, "standardize_s": t2 - t1, "detect_s": t3 - t2, "graph_s": t4 - t3,
           "plan_s": t5 - t4, "impact100_s": t6 - t5, "F1": K.prf(d, T)[2], "waves": len(pl["waves"]),
           "speedup4": K.parallel_speedup(md, pl, 4), "speedup8": K.parallel_speedup(md, pl, 8)}
    out["scalability"].append(row); print("scale", n, round(t3 - t2, 2), "s detect", round(row["F1"], 3))
    conn.close(); os.remove(p)

os.makedirs(os.path.join(ROOT, "results"), exist_ok=True)
json.dump(out, open(os.environ.get("OUT", os.path.join(ROOT, "results", "results.json")), "w"), indent=1, default=list)
print("done")
