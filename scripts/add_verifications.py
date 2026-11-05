"""Append or update provider-page verifications from a compact TSV on stdin:
url<TAB>access_status<TAB>provider<TAB>evidence<TAB>notes(optional)"""
import json, sys
D = sys.argv[1] if len(sys.argv) > 1 else "2026-11-05"
V = json.load(open("data/verifications.json")); by = {e["url"]: e for e in V["entries"]}
n = 0
for line in sys.stdin:
    if not line.strip() or line.startswith("#"): continue
    parts = line.rstrip("\n").split("\t"); parts += [""] * (5 - len(parts))
    url, st, prov, ev, notes = parts[:5]
    e = by.get(url) or {"url": url}
    e.update(access_status=st, provider=prov, cost_evidence=ev, verified_on=D)
    if notes: e["notes"] = notes
    if st in ("paid", "access-uncertain", "retired") and not e.get("replacement"):
        e["action"] = "replacement-pending"
    if url not in by: V["entries"].append(e); by[url] = e
    n += 1
json.dump(V, open("data/verifications.json", "w"), indent=1, ensure_ascii=False)
print(f"{n} rows; {len(V['entries'])} entries total")
