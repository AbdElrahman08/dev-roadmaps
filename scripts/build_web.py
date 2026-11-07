"""Build web/data/catalog.json for the public site.

Only independent content is used: paths and courses written by hand in web/src/,
chosen directly from provider catalogs. A course is shown only when the automated
check found it loads publicly with no paywall or login wall (data/linkcheck.json).
"""
import json, os, time
src = json.load(open("web/src/courses.json"))
paths = json.load(open("web/src/paths.json"))["paths"]
lc = json.load(open("data/linkcheck.json"))["results"] if os.path.exists("data/linkcheck.json") else {}
shown, hidden = [], []
for c in src["courses"]:
    r = lc.get(c["url"])
    ok = bool(r) and r.get("verdict") == "ok" and str(r.get("access", "")).startswith("open")
    c = dict(c, check={"verdict": r.get("verdict") if r else "not checked", "checked_at": r.get("checked_at") if r else None})
    pe = c.get("provider_evidence")
    c["cost"] = "free" if pe and pe["tier"] == "provider-free" else "open"
    (shown if ok else hidden).append(c)
ids = {c["id"] for c in shown}
overviews = json.load(open("web/src/overviews.json")) if os.path.exists("web/src/overviews.json") else {}
tracks = json.load(open("web/src/tracks.json")) if os.path.exists("web/src/tracks.json") else {}
out_paths = []
for p in paths:
    stages = [dict(s, courses=[i for i in s["courses"] if i in ids]) for s in p["stages"]]
    # A zero or final stage whose resources all failed the check is dropped rather than shown empty.
    stages = [s for s in stages if s["courses"] or s.get("kind") == "step"]
    tr = [dict(t, courses=[i for i in t["courses"] if i in ids]) for t in tracks.get(p["id"], [])]
    tr = [t for t in tr if t["courses"] or t["next"]]
    out_paths.append(dict(p, stages=stages, overview=overviews.get(p["id"]), tracks=tr,
                          course_count=len({i for s in stages for i in s["courses"]})))
site = json.load(open("web/src/site.json"))
os.makedirs("web/data", exist_ok=True)
json.dump({"site": site, "built_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "verified_on": src["verified_on"],
           "providers": src["providers"], "courses": shown, "paths": out_paths,
           "hidden": [{"id": c["id"], "title": c["title"], "url": c["url"], "reason": c["check"]["verdict"]} for c in hidden]},
          open("web/data/catalog.json", "w"), ensure_ascii=False, indent=0)
print(f"web catalog: {len(shown)} shown, {len(hidden)} hidden")
