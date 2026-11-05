"""Fetch the loaded roadmap data for every roadmap slug in the upstream repo.

Writes raw JSON to data/pages/<slug>.json and a fetch log to data/pages/_log.json.
Runs in GitHub Actions, which has open network access.
"""
import json, os, sys, time, urllib.request, urllib.error

UPSTREAM = sys.argv[1] if len(sys.argv) > 1 else "upstream"
OUT = "data/pages"
API = "https://roadmap.sh/api/v1-official-roadmap/{}"
UA = "free-dev-roadmaps inventory builder (+https://github.com/AbdElrahman08/free-dev-roadmaps)"

os.makedirs(OUT, exist_ok=True)
slugs = sorted(d for d in os.listdir(os.path.join(UPSTREAM, "roadmaps")) if os.path.isdir(os.path.join(UPSTREAM, "roadmaps", d)))
log = []
for s in slugs:
    url = API.format(s)
    rec = {"slug": s, "url": url}
    for attempt in range(3):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=30) as r:
                body = r.read()
            data = json.loads(body)
            with open(os.path.join(OUT, f"{s}.json"), "wb") as f:
                f.write(body)
            rec.update(status="ok", nodes=len(data.get("nodes", [])), updatedAt=data.get("updatedAt"), title=data.get("title"))
            break
        except urllib.error.HTTPError as e:
            rec.update(status=f"http {e.code}")
            if e.code == 404:
                break
        except Exception as e:  # network or JSON error
            rec.update(status=f"error {type(e).__name__}: {e}")
        time.sleep(2 * (attempt + 1))
    log.append(rec)
    print(s, rec["status"], rec.get("nodes", ""), flush=True)
    time.sleep(0.5)

with open(os.path.join(OUT, "_log.json"), "w") as f:
    json.dump({"fetched_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "results": log}, f, indent=1)
ok = sum(r["status"] == "ok" for r in log)
print(f"fetched {ok}/{len(log)}")
