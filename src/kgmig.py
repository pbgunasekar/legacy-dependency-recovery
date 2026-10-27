"""
kgmig: reference implementation of the Metadata Knowledge Graph-driven migration
framework (Pullur Balu), backend-agnostic (NetworkX in place of Amazon Neptune).

Stages implemented:
  1. Metadata extraction (schema introspection + column profiling)
  2. Canonical standardization (name normalization, type families)
  3. Confidence-aware dependency detection  C(r) = alpha*H(r) + beta*S(r)
  4. Metadata knowledge graph construction (tables/columns as nodes, deps as edges)
  5. Impact analysis (multi-hop reachability)
  6. Dependency-aware sequencing (SCC condensation + topological order, cycle detection)
  7. Parallel migration planning (topological waves)
  8. Execution into a target DB with FK enforcement ON (two-phase load for cycles)
  9. Validation: graph-based checks (recovered dependencies only) and, separately,
     an independent source-to-target audit used as the reference
"""
import re, sqlite3, difflib, math, time
from collections import defaultdict
import networkx as nx

# ---------------------------------------------------------------- 1. extraction
def extract(conn):
    """Schema introspection. Returns dict with tables, columns, pks, declared fks, profiles."""
    md = {"tables": {}, "fks": set()}
    tables = [r[0] for r in conn.execute(
        "select name from sqlite_master where type='table' and name not like 'sqlite_%'")]
    for t in tables:
        cols = conn.execute(f'pragma table_info("{t}")').fetchall()
        pk = [c[1] for c in sorted(cols, key=lambda c: c[5]) if c[5] > 0]
        nrows = conn.execute(f'select count(*) from "{t}"').fetchone()[0]
        prof = {}; nonnull = {}
        for c in cols:
            name, typ = c[1], (c[2] or "")
            vals = [r[0] for r in conn.execute(
                f'select distinct "{name}" from "{t}" where "{name}" is not null')]
            prof[name] = {"type": typ, "distinct": set(vals)}
            nonnull[name] = conn.execute(
                f'select count("{name}") from "{t}"').fetchone()[0]
        md["tables"][t] = {"columns": [c[1] for c in cols], "pk": pk, "rows": nrows,
                           "profile": prof, "ddl_types": {c[1]: (c[2] or "") for c in cols},
                           "notnull": {c[1]: bool(c[3]) for c in cols}, "nonnull_count": nonnull}
        for r in conn.execute(f'pragma foreign_key_list("{t}")'):
            md["fks"].add((t, r[3], r[2], r[4]))  # child, col, parent, pcol
    return md

# ---------------------------------------------------------- 2. standardization
def type_family(typ, sample):
    t = typ.upper()
    if any(k in t for k in ("INT", "NUMERIC", "DEC", "NUMBER", "SMALLINT")):
        return "num"
    if any(k in t for k in ("CHAR", "TEXT", "CLOB", "VARCHAR")):
        return "str"
    if any(k in t for k in ("DATE", "TIME")):
        return "date"
    if any(k in t for k in ("REAL", "FLOA", "DOUB")):
        return "float"
    v = next(iter(sample), None)
    return "num" if isinstance(v, int) else "str" if isinstance(v, str) else "other"

def norm(s):
    s = re.sub(r"([a-z])([A-Z])", r"\1_\2", s).lower()
    toks = [t for t in re.split(r"[^a-z0-9]+", s) if t]
    return toks

def singular(tok):
    if tok.endswith("ies"): return tok[:-3] + "y"
    if tok.endswith("ses"): return tok[:-2]
    if tok.endswith("s") and not tok.endswith("ss"): return tok[:-1]
    return tok

def standardize(md):
    """Canonical model: normalized tokens + type family per column."""
    for t, ti in md["tables"].items():
        ti["tokens"] = [singular(x) for x in norm(t)]
        ti["canon"] = {}
        for c in ti["columns"]:
            p = ti["profile"][c]
            ti["canon"][c] = {"tokens": [singular(x) for x in norm(c)],
                              "family": type_family(p["type"], p["distinct"])}
    return md

# ------------------------------------------------- 3. confidence-aware detection
KEY_SUFFIX = {"id", "no", "num", "nbr", "key", "cd", "code", "ref"}

def name_score(child_tbl, ctoks, ptbl_toks, ktoks):
    """H: heuristic name inference score in [0,1]."""
    c = "".join(ctoks); k = "".join(ktoks); tb = "".join(ptbl_toks)
    if c == k and k not in KEY_SUFFIX:
        return 1.0                       # CustomerID -> Customers.CustomerID
    if c == tb + k or c == tb + "id":
        return 1.0                       # artist_id -> artist.id
    if c.endswith(k) and len(k) > 3 and k not in KEY_SUFFIX:
        return 0.85                      # manager_staff_id -> staff.staff_id
    if tb and tb in c and ctoks[-1] in KEY_SUFFIX:
        return 0.7                       # role-qualified key column naming the table
    # fuzzy: abbreviation / mainframe style (CUSTNO vs CUSTOMER_NO)
    r = max(difflib.SequenceMatcher(None, c, k).ratio(),
            difflib.SequenceMatcher(None, c, tb + k).ratio())
    return round(0.6 * r, 3)

def data_score(cvals, kvals):
    """S: inclusion-dependency based similarity in [0,1]. Returns (S, inclusion)."""
    if not cvals or not kvals:
        return 0.0, 0.0
    inc = len(cvals & kvals) / len(cvals)
    cover = min(1.0, len(cvals) / len(kvals))
    return inc * (0.5 + 0.5 * cover), inc

SAMPLE = 1000

def _keys(md):
    """Single-column keys: declared single-column primary keys, plus keys inferred by
    infer_keys() for tables that declare no primary key (stress test only)."""
    out = [(t, ti["pk"][0]) for t, ti in md["tables"].items() if len(ti["pk"]) == 1]
    out += [(t, k) for t, ti in md["tables"].items() if not ti["pk"] for k in ti.get("inferred_keys", [])]
    return out

def infer_keys(md):
    """For tables without a declared primary key, treat every numeric or string column
    whose values are non-null and unique as a candidate key (a unique column combination
    of size one). Used only in the stress test; off by default."""
    for t, ti in md["tables"].items():
        if ti["pk"] or not ti["rows"]:
            continue
        ti["inferred_keys"] = [c for c in ti["columns"]
                               if ti["canon"][c]["family"] in ("num", "str")
                               and len(ti["profile"][c]["distinct"]) == ti["rows"]
                               and ti["nonnull_count"][c] == ti["rows"]]
    md.pop("_cands", None)
    return md

def candidates(md, sample=SAMPLE):
    """Blocking via an inverted value index (IND discovery) plus a name index.
    Yields (t, c, pt, k, inclusion) for type-compatible pairs that share values,
    and name-matched pairs for columns with no data (inclusion=None)."""
    keys = _keys(md)
    vindex = defaultdict(list)            # (family, value) -> [(pt,k)]
    kname = defaultdict(list)             # normalized key name -> [(pt,k)]
    for pt, k in keys:
        pi = md["tables"][pt]; fam = pi["canon"][k]["family"]
        for v in pi["profile"][k]["distinct"]:
            vindex[(fam, v)].append((pt, k))
        kname["".join(pi["canon"][k]["tokens"])].append((pt, k))
        kname["".join(pi["tokens"]) + "".join(pi["canon"][k]["tokens"])].append((pt, k))
        kname["".join(pi["tokens"]) + "id"].append((pt, k))
    for t, ti in md["tables"].items():
        for c in ti["columns"]:
            if ti["pk"] == [c] or c in ti.get("inferred_keys", ()):
                continue
            cc = ti["canon"][c]; fam = cc["family"]
            if fam not in ("num", "str"):
                continue
            vals = ti["profile"][c]["distinct"]
            if vals:
                sv = sorted(vals, key=lambda x: (str(type(x)), x))
                if sample and len(sv) > sample:
                    step = len(sv) / sample; sv = [sv[int(i * step)] for i in range(sample)]
                hits = defaultdict(int)
                for v in sv:
                    for pk in vindex.get((fam, v), ()):
                        hits[pk] += 1
                for (pt, k), h in hits.items():
                    if (pt, k) != (t, c):
                        yield t, c, pt, k, h / len(sv)
            else:
                cn = "".join(cc["tokens"])
                seen = set()
                for i in range(len(cn)):
                    for pk in kname.get(cn[i:], ()):
                        if pk != (t, c) and pk not in seen:
                            seen.add(pk); yield t, c, pk[0], pk[1], None

def detect(md, method="confidence", alpha=0.5, tau=0.6, min_inc=0.9,
           adaptive=False, h0=0.35, strict_inc=0.95, sample=SAMPLE, use_spec=True):
    """Returns dict edge -> confidence for accepted dependencies (best target per column).
    method: 'name' (naming conventions only), 'data' (partial inclusion dependencies only,
            gate = min_inc), 'confidence' (proposed fusion C = alpha*H + (1-alpha)*S).
    S = inclusion * (0.5*coverage + 0.5*specificity), specificity = 1/#keys that also pass
    the inclusion gate for this column (ambiguity penalty for overlapping surrogate keys)."""
    if method == "name":
        best = {}
        for (t, c, pt, k, _) in name_candidates(md):
            ti, pi = md["tables"][t], md["tables"][pt]
            H = name_score(t, ti["canon"][c]["tokens"], pi["tokens"], pi["canon"][k]["tokens"])
            if H >= 0.85 and H > best.get((t, c), (0,))[0]:
                best[(t, c)] = (H, pt, k)
        return {(t, c, pt, k): s for (t, c), (s, pt, k) in best.items()}
    percol = defaultdict(list)
    cache = md.setdefault("_cands", {})   # cache blocked candidates per sample size
    if sample not in cache:
        cache[sample] = list(candidates(md, sample))
    for (t, c, pt, k, inc) in cache[sample]:
        cv = md["tables"][t]["profile"][c]["distinct"]
        if inc is not None and (not sample or len(cv) <= sample):
            inc = len(cv & md["tables"][pt]["profile"][k]["distinct"]) / len(cv)
        percol[(t, c)].append((pt, k, inc))
    best = {}
    for (t, c), cands in percol.items():
        ti = md["tables"][t]
        passing = [x for x in cands if x[2] is not None and x[2] >= min_inc]
        spec = (1.0 / len(passing) if passing else 0.0) if use_spec else 1.0
        for pt, k, inc in cands:
            pi = md["tables"][pt]
            H = name_score(t, ti["canon"][c]["tokens"], pi["tokens"], pi["canon"][k]["tokens"])
            if inc is None:              # no data profile: name evidence only
                score = H if (method == "confidence" and H >= 0.85) else 0
            elif inc < min_inc:
                score = 0
            else:
                cover = min(1.0, len(ti["profile"][c]["distinct"]) / len(pi["profile"][k]["distinct"]))
                S = inc * (0.5 * cover + 0.5 * spec)
                if method == "data":
                    score = S
                elif adaptive and H < h0:
                    # evidence-adaptive: a name with no signal is neutral, not negative.
                    # Fall back to data evidence, but only for unambiguous, near-complete INDs.
                    score = S if (spec == 1.0 and inc >= strict_inc) else 0
                else:
                    score = alpha * H + (1 - alpha) * S
                if score < tau:
                    score = 0
            if score > 0 and score > best.get((t, c), (0,))[0]:
                best[(t, c)] = (score, pt, k)
    return {(t, c, pt, k): s for (t, c), (s, pt, k) in best.items()}

def name_candidates(md):
    """Name-index lookup for the naming-convention baseline (exact / suffix rules)."""
    keys = _keys(md)
    kname = defaultdict(list)
    for pt, k in keys:
        pi = md["tables"][pt]
        kt = "".join(pi["canon"][k]["tokens"]); tb = "".join(pi["tokens"])
        for n in {kt, tb + kt, tb + "id"}:
            kname[n].append((pt, k))
    for t, ti in md["tables"].items():
        for c in ti["columns"]:
            if ti["pk"] == [c] or c in ti.get("inferred_keys", ()):
                continue
            cn = "".join(ti["canon"][c]["tokens"])
            seen = set()
            for i in range(len(cn)):
                for pk in kname.get(cn[i:], ()):
                    if pk != (t, c) and pk not in seen and \
                       md["tables"][pk[0]]["canon"][pk[1]]["family"] == ti["canon"][c]["family"]:
                        seen.add(pk); yield t, c, pk[0], pk[1], None

def candidate_counts(md, sample=SAMPLE):
    """Number of type-compatible (column, key) pairs before blocking, and number of
    candidates that share at least one value after value-index blocking."""
    keys = _keys(md); fam_keys = defaultdict(int)
    for pt, k in keys:
        fam_keys[md["tables"][pt]["canon"][k]["family"]] += 1
    total = 0; keyset = set(keys)
    for t, ti in md["tables"].items():
        for c in ti["columns"]:
            if ti["pk"] == [c] or c in ti.get("inferred_keys", ()):
                continue
            f = ti["canon"][c]["family"]
            if f in ("num", "str"):
                total += fam_keys[f] - (1 if (t, c) in keyset else 0)
    cache = md.setdefault("_cands", {})
    if sample not in cache:
        cache[sample] = list(candidates(md, sample))
    return total, len(cache[sample])

def prf(pred, truth):
    p = set(pred); tp = len(p & truth)
    P = tp / len(p) if p else 0.0; R = tp / len(truth) if truth else 0.0
    F = 2 * P * R / (P + R) if P + R else 0.0
    return P, R, F, tp, len(p) - tp, len(truth) - tp

# ----------------------------------------------------------- 4. knowledge graph
def build_graph(md, deps):
    G = nx.MultiDiGraph()
    for t, ti in md["tables"].items():
        G.add_node(("T", t), kind="table", rows=ti["rows"])
        for c in ti["columns"]:
            G.add_node(("C", t, c), kind="column")
            G.add_edge(("T", t), ("C", t, c), rel="HAS_COLUMN")
    for (t, c, pt, k), conf in deps.items():
        G.add_edge(("C", t, c), ("C", pt, k), rel="REFERENCES", confidence=conf)
        G.add_edge(("T", t), ("T", pt), rel="DEPENDS_ON", confidence=conf, via=c)
    return G

def table_graph(md, deps):
    D = nx.DiGraph()
    D.add_nodes_from(md["tables"])
    for (t, c, pt, k) in deps:
        if D.has_edge(pt, t):
            D[pt][t]["cols"].append((t, c, k))
        else:
            D.add_edge(pt, t, cols=[(t, c, k)])   # parent -> child (load order)
    return D

# ---------------------------------------------------------- 5. impact analysis
def impact(D, table):
    """Tables affected (multi-hop) if `table` changes = all descendants."""
    return nx.descendants(D, table)

# ------------------------------------------- 6/7. sequencing + parallel planning
def plan(md, deps):
    """SCC condensation -> topological waves. Edges inside an SCC (incl. self loops)
    are 'deferred': the referencing column is loaded NULL and patched in phase 2."""
    D = table_graph(md, deps)
    C = nx.condensation(D)
    deferred = set()
    for scc in C.graph["mapping"].values():
        pass
    members = {n: C.nodes[n]["members"] for n in C.nodes}
    for n, mem in members.items():
        for u in mem:
            for v in mem:
                if D.has_edge(u, v):
                    deferred.update(D[u][v]["cols"])
    cycles = [m for m in members.values() if len(m) > 1] + \
             [{u} for u in D.nodes if D.has_edge(u, u)]
    waves = [sorted(t for n in gen for t in members[n]) for gen in nx.topological_generations(C)]
    order = [t for w in waves for t in w]
    return {"order": order, "waves": waves, "deferred": deferred, "cycles": cycles}

def naive_plan(md):
    order = sorted(md["tables"])
    return {"order": order, "waves": [[t] for t in order], "deferred": set(), "cycles": []}

def ordering_score(order, truth):
    """Sq: fraction of true dependencies whose parent is loaded no later than child."""
    pos = {t: i for i, t in enumerate(order)}
    ok = sum(1 for (t, c, pt, k) in truth if pos[pt] < pos[t] or pt == t)
    return ok / len(truth)

# --------------------------------------------------------------- 8. execution
def migrate(src, md, pl, truth):
    """Load into an in-memory target with the TRUE FKs enforced (immediate).
    Counts rows rejected by referential integrity. Returns stats."""
    tgt = sqlite3.connect(":memory:")
    tgt.execute("pragma foreign_keys=ON")
    fk_by_t = defaultdict(list)
    for (t, c, pt, k) in truth:
        fk_by_t[t].append((c, pt, k))
    for t in md["tables"]:
        ti = md["tables"][t]
        coldefs = []
        for c in ti["columns"]:
            coldefs.append(f'"{c}" {ti["ddl_types"][c]}')
        pk = f', PRIMARY KEY ({",".join(chr(34)+p+chr(34) for p in ti["pk"])})' if ti["pk"] else ""
        fks = "".join(f', FOREIGN KEY ("{c}") REFERENCES "{pt}"("{k}")' for c, pt, k in fk_by_t[t])
        tgt.execute(f'create table "{t}" ({",".join(coldefs)}{pk}{fks})')
    deferred_cols = defaultdict(set)
    for (t, c, k) in pl["deferred"]:
        deferred_cols[t].add(c)
    rejected = 0; loaded = 0; patch = []
    t0 = time.perf_counter()
    for t in pl["order"]:
        cols = md["tables"][t]["columns"]
        q = ",".join(f'"{c}"' for c in cols)
        rows = src.execute(f'select {q} from "{t}"').fetchall()
        dcols = [i for i, c in enumerate(cols) if c in deferred_cols[t]]
        ins = f'insert into "{t}" ({q}) values ({",".join("?"*len(cols))})'
        for r in rows:
            r2 = list(r)
            if dcols:
                patch.append((t, cols, r))
                for i in dcols:
                    r2[i] = None
            try:
                tgt.execute(ins, r2); loaded += 1
            except sqlite3.IntegrityError:
                rejected += 1
    # phase 2: patch deferred (cyclic / self-referencing) columns
    patch_fail = 0
    for t, cols, r in patch:
        pkc = md["tables"][t]["pk"]
        sets = ",".join(f'"{c}"=?' for c in cols if c in deferred_cols[t])
        vals = [r[cols.index(c)] for c in cols if c in deferred_cols[t]]
        where = " and ".join(f'"{p}"=?' for p in pkc)
        try:
            tgt.execute(f'update "{t}" set {sets} where {where}', vals + [r[cols.index(p)] for p in pkc])
        except sqlite3.IntegrityError:
            patch_fail += 1
    elapsed = time.perf_counter() - t0
    return tgt, {"loaded": loaded, "rejected": rejected, "patch_fail": patch_fail, "secs": elapsed}

def final_state(src, tgt, md):
    """Final outcome after both load phases, per source row:
    exact   = present in the target with every value equal to the source,
    altered = present in the target but with at least one value changed (a deferred
              reference left NULL because its second-phase update failed),
    missing = not present in the target (rejected)."""
    from collections import Counter
    exact = altered = missing = 0
    for t, ti in md["tables"].items():
        q = ",".join(f'"{c}"' for c in ti["columns"])
        s = Counter(src.execute(f'select {q} from "{t}"').fetchall())
        g = Counter(tgt.execute(f'select {q} from "{t}"').fetchall())
        e = sum((s & g).values())
        exact += e; altered += sum(g.values()) - e; missing += sum(s.values()) - sum(g.values())
    return {"exact": exact, "altered": altered, "missing": missing}

# --------------------------------------------------------------- 9. validation
def _key_cols(md, t):
    ti = md["tables"][t]
    return ti["pk"] if ti["pk"] else ti["columns"]

def load_unenforced(src, md, order):
    """Copy every row in plan order with constraints disabled, as production loaders
    commonly do before validating."""
    tgt = sqlite3.connect(":memory:")
    for t in order:
        ti = md["tables"][t]
        tgt.execute(f'create table "{t}" ({",".join(chr(34)+c+chr(34)+" "+ti["ddl_types"][c] for c in ti["columns"])})')
        q = ",".join(f'"{c}"' for c in ti["columns"])
        tgt.executemany(f'insert into "{t}" values ({",".join("?"*len(ti["columns"]))})',
                        src.execute(f'select {q} from "{t}"'))
    return tgt

def _orphan_rows(conn, md, t, c, pt, k):
    kc = ",".join(f'x."{p}"' for p in _key_cols(md, t))
    return set(conn.execute(
        f'select {kc} from "{t}" x where x."{c}" is not null and not exists '
        f'(select 1 from "{pt}" p where p."{k}" = x."{c}")').fetchall())

def graph_validate(src, tgt, md, deps):
    """Validation driven by the recovered graph only.
    Lineage paths: (1) per table, source key set vs target key set (missing rows);
    (2) per recovered dependency, target rows whose reference has no parent (orphans).
    Returns the missing row keys per table and the flagged rows per recovered edge."""
    missing = {}
    for t in md["tables"]:
        kc = ",".join(f'"{p}"' for p in _key_cols(md, t))
        a = set(src.execute(f'select {kc} from "{t}"').fetchall())
        b = set(tgt.execute(f'select {kc} from "{t}"').fetchall())
        missing[t] = a - b
    flagged = {e: _orphan_rows(tgt, md, *e) for e in deps}
    return missing, flagged

def audit(src, tgt, md, truth):
    """Independent source-to-target audit used as the reference: compares every row in
    full and checks referential integrity along the true dependencies."""
    from collections import Counter
    diff = {}
    for t, ti in md["tables"].items():
        q = ",".join(f'"{c}"' for c in ti["columns"])
        s = Counter(src.execute(f'select {q} from "{t}"').fetchall())
        g = Counter(tgt.execute(f'select {q} from "{t}"').fetchall())
        diff[t] = (s - g, g - s)           # rows missing/changed, rows unexpected/changed
    orphans = {e: _orphan_rows(tgt, md, *e) for e in truth}
    return diff, orphans

def parallel_speedup(md, pl, workers=4):
    """Cost model: table cost = rows. Sequential = sum; parallel = sum over waves of
    LPT-scheduled makespan on `workers`."""
    cost = {t: max(1, md["tables"][t]["rows"]) for t in md["tables"]}
    seq = sum(cost.values()); par = 0
    for w in pl["waves"]:
        bins = [0] * workers
        for t in sorted(w, key=lambda x: -cost[x]):
            bins[bins.index(min(bins))] += cost[t]
        par += max(bins)
    return seq / par
