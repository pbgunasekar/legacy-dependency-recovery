"""Supervised feature-classifier baseline in the spirit of Rostin et al. (WebDB 2009).

This is not a reproduction of their system. It follows their design: candidate pairs from
inclusion dependencies are described by ten features modeled on theirs (F1-F10) and
classified with a decision tree trained on databases whose foreign keys are known.
Here the training databases are the development seeds (101-103) of both synthetic
profiles; the classifier is never trained on test seeds or public datasets.

Two candidate modes:
  exact   - only exact inclusion dependencies (inclusion = 1), as in Rostin et al.
  partial - inclusion >= the same gate the proposed method uses (adapted to dirty data)
"""
import difflib, math
from collections import defaultdict
from sklearn.tree import DecisionTreeClassifier
import kgmig as K

FEATURES = ["log_distinct_dep", "coverage", "multi_dependent", "multi_referenced",
            "name_similarity", "value_length_diff", "out_of_range", "typical_suffix",
            "table_size_ratio", "inclusion"]

def _inclusions(md, sample):
    cache = md.setdefault("_cands", {})
    if sample not in cache:
        cache[sample] = list(K.candidates(md, sample))
    out = []
    for (t, c, pt, k, inc) in cache[sample]:
        if inc is None:
            continue
        cv = md["tables"][t]["profile"][c]["distinct"]
        if not sample or len(cv) <= sample:
            inc = len(cv & md["tables"][pt]["profile"][k]["distinct"]) / len(cv)
        out.append((t, c, pt, k, inc))
    return out

def _len(v):
    return len(str(v))

def _colstats(md, t, c):
    """Mean value length and value range of a column, cached (pure speed-up)."""
    cache = md.setdefault("_colstats", {})
    if (t, c) not in cache:
        v = md["tables"][t]["profile"][c]["distinct"]
        try:
            rng = (min(v), max(v))
        except (TypeError, ValueError):
            rng = None
        cache[(t, c)] = (sum(map(_len, v)) / len(v) if v else 0.0, rng)
    return cache[(t, c)]

def features(md, mode="partial", gate=0.6, sample=K.SAMPLE):
    lo = 0.999 if mode == "exact" else gate
    cands = [x for x in _inclusions(md, sample) if x[4] >= lo]
    dep_count = defaultdict(int); ref_count = defaultdict(int)
    for t, c, pt, k, inc in cands:
        dep_count[(t, c)] += 1; ref_count[(pt, k)] += 1
    rows, keys = [], []
    for t, c, pt, k, inc in cands:
        ti, pi = md["tables"][t], md["tables"][pt]
        cv, kv = ti["profile"][c]["distinct"], pi["profile"][k]["distinct"]
        cn = "".join(ti["canon"][c]["tokens"]); kn = "".join(pi["canon"][k]["tokens"])
        sim = difflib.SequenceMatcher(None, cn, kn).ratio()
        (lc, _), (lk, krng) = _colstats(md, t, c), _colstats(md, pt, k)
        ldiff = abs(lc - lk)
        try:
            oor = sum(1 for v in cv if v < krng[0] or v > krng[1]) / len(cv) if krng else 0.0
        except TypeError:
            oor = 0.0
        suffix = 1.0 if ti["canon"][c]["tokens"] and ti["canon"][c]["tokens"][-1] in K.KEY_SUFFIX else 0.0
        size_ratio = ti["rows"] / max(1, pi["rows"])
        rows.append([math.log1p(len(cv)), min(1.0, len(cv) / len(kv)), dep_count[(t, c)],
                     ref_count[(pt, k)], sim, ldiff, oor, suffix, size_ratio, inc])
        keys.append((t, c, pt, k))
    return keys, rows

def train(dev, mode="partial", gate=0.6):
    """dev: list of (md, truth). Returns a fitted decision tree."""
    X, y = [], []
    for md, T in dev:
        ks, rs = features(md, mode, gate)
        X += rs; y += [1 if e in T else 0 for e in ks]
    clf = DecisionTreeClassifier(max_depth=8, min_samples_leaf=5, random_state=0)
    clf.fit(X, y)
    return clf

def detect_classifier(md, clf, mode="partial", gate=0.6, threshold=0.5):
    ks, rs = features(md, mode, gate)
    if not rs:
        return {}
    proba = clf.predict_proba(rs)[:, list(clf.classes_).index(1)] if 1 in clf.classes_ else [0] * len(rs)
    # one target per column, as for every method; ties in probability (frequent with a
    # decision tree) are broken by name similarity, then by inclusion, never by input order
    best = {}
    for (t, c, pt, k), p, r in zip(ks, proba, rs):
        score = (p, r[FEATURES.index("name_similarity")], r[FEATURES.index("inclusion")])
        if p >= threshold and score > best.get((t, c), ((0,),))[0]:
            best[(t, c)] = (score, pt, k)
    return {(t, c, pt, k): sc[0] for (t, c), (sc, pt, k) in best.items()}
