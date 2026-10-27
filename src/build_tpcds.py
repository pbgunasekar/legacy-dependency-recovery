"""Builds the TPC-DS dataset used in the experiments: schemas/tpcds_sf1.db

Steps (all deterministic):
  1. clone the open-source TPC-DS kit mirror (github.com/gregrahn/tpcds-kit) at a pinned commit
  2. build dsdgen (gcc -fcommon for modern compilers)
  3. generate data at scale factor 1 with a fixed RNG seed and verify every .dat file's SHA-256
  4. load into SQLite: dimension tables in full, the 7 fact tables stride-sampled to FACT_ROWS rows
  5. declare primary keys from tpcds.sql and foreign keys from tpcds_ri.sql (ground truth)

Note: this uses the TPC-DS schema and data generator under the TPC EULA. Results produced with it
are research measurements, not TPC-DS benchmark results.
"""
import hashlib, json, os, re, sqlite3, subprocess, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KIT_URL = "https://github.com/gregrahn/tpcds-kit.git"
KIT_COMMIT = "5a3a81796992b725c2a8b216767e142609966752"
SCALE, RNGSEED, FACT_ROWS = 1, 19620718, 50000
FACTS = {"store_sales", "store_returns", "catalog_sales", "catalog_returns",
         "web_sales", "web_returns", "inventory"}
WORK = os.path.join(ROOT, "build", "tpcds")
KIT = os.path.join(WORK, "tpcds-kit")
DAT = os.path.join(WORK, f"sf{SCALE}")
OUT = os.path.join(ROOT, "schemas", f"tpcds_sf{SCALE}.db")
CHECKSUMS = os.path.join(ROOT, "src", "tpcds_sf1_checksums.json")

def sh(cmd, cwd=None):
    print("+", " ".join(cmd)); subprocess.run(cmd, cwd=cwd, check=True)

def build_kit():
    if not os.path.exists(os.path.join(KIT, "tools", "dsdgen")):
        os.makedirs(WORK, exist_ok=True)
        if not os.path.exists(KIT):
            sh(["git", "clone", "-q", KIT_URL, KIT])
        sh(["git", "checkout", "-q", KIT_COMMIT], cwd=KIT)
        sh(["make", "OS=LINUX", "LINUX_CFLAGS=-g -Wall -fcommon", "dsdgen"], cwd=os.path.join(KIT, "tools"))

def generate():
    if not os.path.exists(os.path.join(DAT, "store_sales.dat")):
        os.makedirs(DAT, exist_ok=True)
        sh(["./dsdgen", "-scale", str(SCALE), "-dir", DAT, "-force", "-rngseed", str(RNGSEED)],
           cwd=os.path.join(KIT, "tools"))
    sums = {f: hashlib.sha256(open(os.path.join(DAT, f), "rb").read()).hexdigest()
            for f in sorted(os.listdir(DAT)) if f.endswith(".dat") and f != "dbgen_version.dat"}
    if os.path.exists(CHECKSUMS):
        ref = json.load(open(CHECKSUMS))
        bad = [f for f in ref if sums.get(f) != ref[f]]
        if bad:
            sys.exit(f"TPC-DS data checksum mismatch: {bad}")
        print("TPC-DS .dat checksums: OK")
    else:
        json.dump(sums, open(CHECKSUMS, "w"), indent=1); print("wrote", CHECKSUMS)

def parse_ddl():
    sql = open(os.path.join(KIT, "tools", "tpcds.sql")).read()
    tables = {}
    for name, body in re.findall(r"create table (\w+)\s*\((.*?)\);", sql, re.S):
        if name == "dbgen_version":
            continue
        cols, pk = [], []
        for line in body.split("\n"):
            line = line.strip().rstrip(",")
            m = re.match(r"primary key\s*\((.*)\)", line)
            if m:
                pk = [c.strip() for c in m.group(1).split(",")]
            elif line and not line.startswith("--"):
                p = line.split()
                cols.append((p[0], p[1]))
        tables[name] = {"cols": cols, "pk": pk}
    ri = open(os.path.join(KIT, "tools", "tpcds_ri.sql")).read()
    fks = re.findall(r"alter table (\w+) add constraint \w+ foreign key\s*\((\w+)\) references (\w+)\s*\((\w+)\)", ri)
    colset = {t: {c for c, _ in ti["cols"]} for t, ti in tables.items()}
    invalid = [f for f in fks if f[1] not in colset.get(f[0], ()) or f[3] not in colset.get(f[2], ())]
    # Known erratum in tpcds_ri.sql: 2 constraints name columns absent from tpcds.sql
    # (catalog_page.cp_promo_id, catalog_returns.cr_ship_date_sk). They are excluded.
    print(f"excluded {len(invalid)} invalid FK definitions: {invalid}")
    return tables, [f for f in fks if f not in invalid]

def sqltype(t):
    t = t.lower()
    if t.startswith("integer"): return "INTEGER"
    if t.startswith("decimal"): return "DECIMAL" + t[7:].upper()
    if t.startswith("char") or t.startswith("varchar"): return "VARCHAR" + t[t.index("("):].upper() if "(" in t else "VARCHAR"
    if t.startswith("date"): return "DATE"
    if t.startswith("time"): return "TIME"
    return t.upper()

def load(tables, fks):
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    if os.path.exists(OUT): os.remove(OUT)
    db = sqlite3.connect(OUT)
    fk_by = {}
    for t, c, pt, pc in fks:
        fk_by.setdefault(t, []).append((c, pt, pc))
    for t, ti in tables.items():
        cols = ",".join(f'"{c}" {sqltype(ty)}' for c, ty in ti["cols"])
        pk = f', PRIMARY KEY ({",".join(ti["pk"])})' if ti["pk"] else ""
        fk = "".join(f', FOREIGN KEY ("{c}") REFERENCES "{pt}"("{pc}")' for c, pt, pc in fk_by.get(t, []))
        db.execute(f'create table "{t}" ({cols}{pk}{fk})')
        types = [sqltype(ty) for _, ty in ti["cols"]]
        path = os.path.join(DAT, t + ".dat")
        n_total = sum(1 for _ in open(path, encoding="latin-1"))
        stride = -(-n_total // FACT_ROWS) if t in FACTS else 1   # ceil -> at most FACT_ROWS rows
        def rows():
            seen = set()
            with open(path, encoding="latin-1") as f:
                for i, line in enumerate(f):
                    if i % stride:
                        continue
                    vals = line.rstrip("\n").split("|")[:len(types)]
                    out = []
                    for v, ty in zip(vals, types):
                        if v == "":
                            out.append(None)
                        elif ty == "INTEGER":
                            out.append(int(v))
                        elif ty.startswith("DECIMAL"):
                            out.append(float(v))
                        else:
                            out.append(v)
                    key = tuple(out[[c for c, _ in ti["cols"]].index(p)] for p in ti["pk"])
                    if ti["pk"] and key in seen:      # guard against duplicate PKs after sampling
                        continue
                    seen.add(key); yield out
        db.executemany(f'insert into "{t}" values ({",".join("?" * len(types))})', rows())
        db.commit()
        print(f"  {t}: {db.execute(f'select count(*) from {t}').fetchone()[0]:,} rows"
              + (f" (stride {stride} of {n_total:,})" if stride > 1 else ""))
    db.execute("vacuum"); db.close()
    print("wrote", OUT, f"({len(tables)} tables, {len(fks)} declared FKs)")

if __name__ == "__main__":
    build_kit(); generate(); load(*parse_ddl())
