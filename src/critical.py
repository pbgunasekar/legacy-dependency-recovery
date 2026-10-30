"""Migration-critical dependency analysis (added in revision 3; no new data or parameters).

A true dependency e = (t, c, pt, k) that a graph misses is *migration-critical* for the
plan derived from that graph if the plan does not satisfy it: the parent table pt is not
loaded strictly before the child table t, and the column c is not deferred to the second
loading phase. (A missed self-reference is therefore always critical unless another
recovered edge makes c deferred.) A missed dependency whose order the plan satisfies
anyway, because other recovered dependencies or the tie order place the parent first,
cannot cause a referential rejection and is *non-critical*.

The analysis re-runs the frozen detection (deterministic) on the public datasets and on
the SynthLegacy/SynthModern test seeds, checks that the missed dependencies equal those
recorded in results/results.json, and writes results/critical.json.
"""
import json
import os
import sqlite3
import statistics as st
import sys

sys.path.insert(0, os.path.dirname(__file__))
import kgmig as K
import synth as S

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = json.load(open(os.path.join(ROOT, "params.json")))
A = P["adaptive"]
ADAPT = dict(method="confidence", alpha=A["alpha"], tau=A["tau"], min_inc=A["min_inc"],
             adaptive=True, h0=A["h0"], strict_inc=A["strict_inc"])
GRAPHS = {"Graph: Proposed": ADAPT, "Graph: Name-only": dict(method="name")}
PUBLIC = {"Chinook": "chinook.db", "Northwind": "northwind.db", "Sakila": "sakila.db",
          "TPC-DS": "tpcds_sf1.db"}
SYNTH = {"SynthModern-100": "modern", "SynthLegacy-100": "legacy"}
TEST_SEEDS = [201, 202, 203, 204, 205]


def classify(md, truth, deps):
    pl = K.plan(md, deps)
    pos = {t: i for i, t in enumerate(pl["order"])}
    missed = sorted(truth - set(deps))
    crit = [e for e in missed
            if not (pos[e[2]] < pos[e[0]]) and (e[0], e[1], e[3]) not in pl["deferred"]]
    return {"true": len(truth), "missed": len(missed), "critical": len(crit),
            "critical_deps": [list(e) for e in crit],
            "noncritical_deps": [list(e) for e in missed if e not in crit]}


def main():
    recorded = json.load(open(os.path.join(ROOT, "results", "results.json")))
    out = {"public": {}, "synthetic": {}}
    for nm, f in PUBLIC.items():
        conn = sqlite3.connect(os.path.join(ROOT, "schemas", f))
        md = K.standardize(K.extract(conn))
        T = md["fks"]
        out["public"][nm] = {}
        for g, kw in GRAPHS.items():
            deps = K.detect(md, **kw)
            r = classify(md, T, deps)
            if g == "Graph: Proposed":       # consistency with the recorded run
                rec = sorted(map(tuple, recorded["public"][nm]["missed_by_proposed"]))
                assert sorted(truth_tuple for truth_tuple in (T - set(deps))) == rec, nm
            r["exact"] = recorded["public"][nm]["migration"][g]["exact"]
            r["source_rows"] = recorded["public"][nm]["migration"][g]["source_rows"]
            out["public"][nm][g] = r
        conn.close()
        print(nm, {g: (v["missed"], v["critical"]) for g, v in out["public"][nm].items()}, flush=True)
    for dname, prof in SYNTH.items():
        per = {g: [] for g in GRAPHS}
        for seed in TEST_SEEDS:
            conn, T = S.generate(":memory:", 100, prof, seed)
            md = K.standardize(K.extract(conn))
            for g, kw in GRAPHS.items():
                r = classify(md, T, K.detect(md, **kw))
                per[g].append({k: r[k] for k in ("true", "missed", "critical")})
            conn.close()
        out["synthetic"][dname] = {}
        for g in GRAPHS:
            rows = per[g]
            out["synthetic"][dname][g] = {k: st.mean(r[k] for r in rows) for k in ("true", "missed", "critical")}
            out["synthetic"][dname][g]["exact"] = recorded["synthetic"][dname]["migration"][g]["exact"]
            out["synthetic"][dname][g]["per_seed"] = rows
        print(dname, {g: (v["missed"], v["critical"]) for g, v in out["synthetic"][dname].items()}, flush=True)
    json.dump(out, open(os.path.join(ROOT, "results", "critical.json"), "w"), indent=1)


if __name__ == "__main__":
    main()
