"""Unit and invariant tests. Run: pytest -q (needs schemas/ from src/fetch_data.py)."""
import json
import os
import sqlite3
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
import kgmig as K  # noqa: E402

P = json.load(open(os.path.join(ROOT, "params.json")))["adaptive"]
ADAPT = dict(method="confidence", alpha=P["alpha"], tau=P["tau"], min_inc=P["min_inc"],
             adaptive=True, h0=P["h0"], strict_inc=P["strict_inc"])


# ---------------------------------------------------------------- unit tests
def toks(s):
    return [K.singular(x) for x in K.norm(s)]


def test_naming_rules():
    assert K.name_score("Invoice", toks("CustomerId"), toks("Customer"), toks("CustomerId")) == 1.0     # R1
    assert K.name_score("store", toks("manager_staff_id"), toks("staff"), toks("staff_id")) == 0.85     # R2
    assert K.name_score("x", toks("owner_customer_no"), toks("customer"), toks("cust_key")) == 0.7      # R3
    assert K.name_score("x", toks("XREF_CD3"), toks("customer"), toks("cust_no")) < 0.7                # weak


def test_data_score():
    assert K.data_score({1, 2}, {1, 2, 3, 4}) == (1.0 * (0.5 + 0.5 * 0.5), 1.0)
    s, inc = K.data_score({1, 9}, {1, 2})
    assert inc == 0.5
    assert K.data_score(set(), {1}) == (0.0, 0.0)


def _md(tables):
    return {"tables": {t: {"rows": 1, "columns": [], "pk": ["id"]} for t in tables}}


def test_plan_defers_cycles_and_orders_parents_first():
    md = _md(["a", "b", "c", "d"])
    deps = {("b", "a_id", "a", "id"): 1, ("c", "b_id", "b", "id"): 1,      # a -> b -> c
            ("a", "d_id", "d", "id"): 1, ("d", "a_id", "a", "id"): 1,      # cycle a <-> d
            ("c", "parent", "c", "id"): 1}                                  # self reference
    pl = K.plan(md, deps)
    pos = {t: i for i, t in enumerate(pl["order"])}
    assert pos["a"] < pos["b"] < pos["c"]
    assert ("c", "parent", "id") in pl["deferred"]
    assert {("a", "d_id", "id"), ("d", "a_id", "id")} <= pl["deferred"]
    # every non-deferred edge is satisfied by the order
    for (t, c, pt, k) in deps:
        assert (t, c, k) in pl["deferred"] or pos[pt] < pos[t]


# ---------------------------------------------------------------- invariants on a real schema
@pytest.fixture(scope="module")
def chinook():
    path = os.path.join(ROOT, "schemas", "chinook.db")
    if not os.path.exists(path):
        pytest.skip("run src/fetch_data.py first")
    conn = sqlite3.connect(path)
    md = K.standardize(K.extract(conn))
    yield conn, md
    conn.close()


def test_detection_is_deterministic(chinook):
    _, md = chinook
    assert K.detect(md, **ADAPT) == K.detect(md, **ADAPT)


def test_declared_constraints_are_hidden(chinook):
    _, md = chinook
    d = K.detect(md, **ADAPT)
    assert len(md["fks"]) == 11 and len(set(d) & md["fks"]) == 9    # as reported in the paper


def test_final_state_accounts_for_every_row(chinook):
    conn, md = chinook
    T = md["fks"]
    pl = K.plan(md, K.detect(md, **ADAPT))
    tgt, stt = K.migrate(conn, md, pl, T)
    fs = K.final_state(conn, tgt, md)
    assert fs["exact"] + fs["altered"] + fs["missing"] == stt["loaded"] + stt["rejected"]
    true_pl = K.plan(md, {e: 1 for e in T})
    tgt2, _ = K.migrate(conn, md, true_pl, T)
    assert K.final_state(conn, tgt2, md)["missing"] == 0             # ground-truth plan loses nothing here
