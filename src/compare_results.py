"""Compare a fresh results/results.json with the published one, ignoring wall-clock timings
and the environment block. Exit code 0 if every accuracy, migration, validation and stress
value is identical.

  python src/compare_results.py published.json results/results.json
  python src/compare_results.py --digest results/results.json   # print the canonical digest
"""
import hashlib
import json
import sys

TIMING = ("_s", "secs", "time", "seconds", "speed")


def skip(k):
    return k == "environment" or any(t in k for t in TIMING)


def canonical(x):
    if isinstance(x, dict):
        return {k: canonical(v) for k, v in sorted(x.items()) if not skip(k)}
    if isinstance(x, list):
        return [canonical(v) for v in x]
    if isinstance(x, float):
        return round(x, 9)
    return x


def digest(path):
    return hashlib.sha256(json.dumps(canonical(json.load(open(path))), sort_keys=True).encode()).hexdigest()


def diff(a, b, p=""):
    out = []
    if isinstance(a, dict) and isinstance(b, dict):
        for k in sorted(set(a) | set(b)):
            out += diff(a.get(k), b.get(k), f"{p}/{k}")
    elif isinstance(a, list) and isinstance(b, list) and len(a) == len(b):
        for i, (u, v) in enumerate(zip(a, b)):
            out += diff(u, v, f"{p}[{i}]")
    elif a != b:
        out.append((p, a, b))
    return out


if __name__ == "__main__":
    if sys.argv[1] == "--digest":
        print(digest(sys.argv[2]))
        sys.exit(0)
    a, b = (canonical(json.load(open(f))) for f in sys.argv[1:3])
    d = diff(a, b)
    print("NON-TIMING DIFFERENCES:", len(d))
    for x in d[:30]:
        print(x)
    sys.exit(1 if d else 0)
