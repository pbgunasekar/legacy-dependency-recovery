"""Tune on DEV seeds 101-103 only (60 tables, modern+legacy)."""
import sys, os, json
sys.path.insert(0, os.path.dirname(__file__))
import kgmig as K, synth as S
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
dev = []
for prof in ["modern", "legacy"]:
    for seed in [101, 102, 103]:
        p = os.path.join(ROOT, "synth", f"dev_{prof}_{seed}.db")
        if os.path.exists(p): os.remove(p)
        c, T = S.generate(p, 60, prof, seed); dev.append((K.standardize(K.extract(c)), T))
mf = lambda **kw: sum(K.prf(K.detect(md, **kw), T)[2] for md, T in dev) / len(dev)
P = json.load(open(os.path.join(ROOT, "params.json")))
best = None
for a in [0.3, 0.4, 0.5, 0.6, 0.7, 0.8]:
    for tau in [0.35, 0.4, 0.45, 0.5, 0.55, 0.6]:
        for mi in [0.6, 0.7, 0.8]:
            for h0 in [0.3, 0.35, 0.4]:
                for si in [0.9, 0.95]:
                    f = mf(method="confidence", alpha=a, tau=tau, min_inc=mi, adaptive=True, h0=h0, strict_inc=si)
                    if not best or f > best[0]: best = (f, a, tau, mi, h0, si)
print("adaptive best", best)
P["adaptive"] = dict(zip(["devF1", "alpha", "tau", "min_inc", "h0", "strict_inc"], best))
json.dump(P, open(os.path.join(ROOT, "params.json"), "w"), indent=1)
