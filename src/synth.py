"""Synthetic legacy-schema generator with planted ground-truth dependencies.

Naming styles for a referencing column (child -> parent key):
  clean  : same name as parent key           (CUST_NO -> CUSTMAST.CUST_NO)
  abbrev : vowel-stripped / truncated name   (CST_NO, CUSTNO)
  role   : role-qualified                    (OWNER_CUST_NO, PRIM_ACCT_NO)
  opaque : no name signal                    (XREF_CD3, LINK_KEY_2)
Noise columns (small-int codes, amounts, external refs) create value overlap.
Profiles 'modern' and 'legacy' mix the styles differently.
"""
import random, sqlite3

LAST_STYLES = {}

WORDS = ["cust", "acct", "fund", "trade", "posn", "txn", "hold", "plan", "brkr", "agent",
         "addr", "pay", "fee", "div", "stmt", "tax", "lot", "secy", "branch", "rep",
         "order", "exch", "chan", "doc", "corr", "beneficiary", "trust", "share", "class", "pric"]
SUFFIX = ["mast", "hist", "dtl", "xref", "ctl", "rel", "log", "tbl", "ext", "sum"]
PROFILES = {
    "modern": {"clean": 0.80, "abbrev": 0.10, "role": 0.10, "opaque": 0.00},
    "legacy": {"clean": 0.25, "abbrev": 0.30, "role": 0.25, "opaque": 0.20},
}
ROLES = ["owner", "prim", "sec", "src", "tgt", "parent", "orig", "curr", "alt", "mgr"]

def _abbrev(name, rnd):
    stem, _, suf = name.rpartition("_")
    s = stem[0] + "".join(ch for ch in stem[1:] if ch not in "aeiou")
    return rnd.choice([f"{s}_{suf}", f"{stem}{suf}", f"{stem[:3]}_{suf}"])

def generate(path, n_tables=50, profile="legacy", seed=0, rows=(20, 400),
             string_key_frac=0.5, orphan_rate=0.02, cycle_rate=0.03, self_rate=0.03,
             noise_cols=3):
    rnd = random.Random(seed)
    LAST_STYLES.clear()
    mix = PROFILES[profile]
    styles = list(mix); weights = [mix[s] for s in styles]
    tables = []
    used = set()
    for i in range(n_tables):
        while True:
            nm = f"{rnd.choice(WORDS)}_{rnd.choice(SUFFIX)}"
            if nm not in used:
                break
            nm = f"{nm}{i}"
            if nm not in used:
                break
        used.add(nm)
        base = nm.split("_")[0]
        key = f"{base}_{rnd.choice(['no', 'id', 'key', 'nbr'])}"
        if key in {t['key'] for t in tables}:
            key = f"{base}{i}_{key.split('_')[1]}"
        n = rnd.randint(*rows)
        strkey = rnd.random() < string_key_frac
        if strkey:
            pref = base[:2].upper()
            ids = [f"{pref}{rnd.randint(0, 10**7):08d}" for _ in range(n)]
            ids = list(dict.fromkeys(ids))
        else:
            ids = list(range(1, len(range(n)) + 1))
        tables.append({"name": nm, "key": key, "ids": ids, "str": strkey, "cols": [], "fks": []})
    # dependencies: DAG over index order (parent index < child index) + back edges + self refs
    truth = set()
    for ci, ch in enumerate(tables):
        if ci == 0:
            continue
        nparents = rnd.choice([0, 1, 1, 2, 2, 3])
        parents = rnd.sample(range(ci), min(nparents, ci))
        if rnd.random() < cycle_rate and ci + 1 < n_tables:
            parents.append(rnd.randrange(ci + 1, n_tables))
        for pi in parents:
            _add_fk(ch, tables[pi], styles, weights, rnd)
        if rnd.random() < self_rate:
            ch["fks"].append((f"{rnd.choice(ROLES)}_{ch['key']}", ch, "self"))
    conn = sqlite3.connect(path)
    for t in tables:
        cols = [(t["key"], "VARCHAR(10)" if t["str"] else "INTEGER")]
        names = {t["key"]}
        fkcols = []
        for (cname, p, st) in t["fks"]:
            base = cname; j = 2
            while cname in names:
                cname = f"{base}{j}"; j += 1
            names.add(cname)
            cols.append((cname, "VARCHAR(10)" if p["str"] else "INTEGER"))
            fkcols.append((cname, p))
            truth.add((t["name"], cname, p["name"], p["key"]))
            LAST_STYLES[(t["name"], cname, p["name"], p["key"])] = st
        noise = []
        for j in range(noise_cols):
            kind = rnd.choice(["status_cd", "qty", "amt", "ext_ref", "seq_nbr", "type_cd"])
            cname = f"{kind}{j}"
            names.add(cname)
            noise.append((cname, kind))
            cols.append((cname, "INTEGER" if kind != "amt" else "DECIMAL(12,2)"))
        conn.execute(f'create table "{t["name"]}" ('
                     + ",".join(f'"{c}" {ty}' for c, ty in cols)
                     + f', primary key ("{t["key"]}"))')
        rows_out = []
        for kid in t["ids"]:
            r = [kid]
            for cname, p in fkcols:
                if p is t:
                    r.append(rnd.choice(t["ids"]) if rnd.random() < 0.7 else None)
                elif rnd.random() < orphan_rate:
                    r.append(f"ZZ{rnd.randint(0, 10**7):08d}" if p["str"] else 10**6 + rnd.randint(0, 999))
                else:
                    r.append(rnd.choice(p["ids"][: max(1, int(len(p["ids"]) * rnd.uniform(0.3, 1)))]))
            for cname, kind in noise:
                if kind in ("status_cd", "type_cd"):
                    r.append(rnd.randint(1, rnd.choice([3, 5, 9])))
                elif kind == "qty":
                    r.append(rnd.randint(1, 50))
                elif kind == "seq_nbr":
                    r.append(rnd.randint(1, 300))
                elif kind == "ext_ref":
                    r.append(rnd.randint(1, 5000))
                else:
                    r.append(round(rnd.uniform(1, 10000), 2))
            rows_out.append(r)
        conn.executemany(f'insert into "{t["name"]}" values ({",".join("?" * len(cols))})', rows_out)
    conn.commit()
    return conn, truth

def _add_fk(ch, p, styles, weights, rnd):
    st = rnd.choices(styles, weights)[0]
    k = p["key"]
    if st == "clean":
        name = k
    elif st == "abbrev":
        name = _abbrev(k, rnd)
    elif st == "role":
        name = f"{rnd.choice(ROLES)}_{k}"
    else:
        name = f"{rnd.choice(['xref', 'link', 'rel', 'ptr'])}_{rnd.choice(['cd', 'key', 'val'])}{rnd.randint(1, 9)}"
    ch["fks"].append((name, p, st))
