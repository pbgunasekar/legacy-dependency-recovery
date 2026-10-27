"""Download the three public sample databases (TPC-DS is built separately by build_tpcds.py) and verify SHA-256 checksums,
so every run uses byte-identical inputs."""
import hashlib, os, sys, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = {
    "chinook.db": ("https://raw.githubusercontent.com/lerocha/chinook-database/master/ChinookDatabase/DataSources/Chinook_Sqlite.sqlite",
                              "7651ba378ac2fcd0dfc3c66fb101f7a7eed3ba39a612ec642b96e20702061f15"),
    "northwind.db": ("https://raw.githubusercontent.com/jpwhite3/northwind-SQLite3/main/dist/northwind.db",
                     "2f4f5c68dfcd33ba27373eae48c7a4869800c68095ee0f9f0da494f83382a877"),
    "sakila.db": ("https://raw.githubusercontent.com/bradleygrant/sakila-sqlite3/main/sakila_master.db",
                         "88c91a4a1a6b61f9d3f35904c0a173c887b25e73f20c3c2fdb073818c06f4268"),
}
os.makedirs(os.path.join(ROOT, "schemas"), exist_ok=True)
ok = True
for name, (url, sha) in DATA.items():
    path = os.path.join(ROOT, "schemas", name)
    if not os.path.exists(path):
        print("downloading", name); urllib.request.urlretrieve(url, path)
    got = hashlib.sha256(open(path, "rb").read()).hexdigest()
    status = "OK" if got == sha else "CHECKSUM MISMATCH (upstream file changed)"
    ok &= got == sha
    print(f"{name}: {status}")
sys.exit(0 if ok else 1)
