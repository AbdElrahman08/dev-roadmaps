"""Automated link check for every URL in the inventory.

Verdicts
  ok       final response 2xx/3xx
  broken   404/410 or DNS failure: the page is gone
  blocked  401/403/429/451/999: the site refuses bots; inconclusive, re-check in a browser
  error    timeout, TLS or other network error: inconclusive
Results are incremental: URLs checked within MAX_AGE_DAYS are skipped.
"""
import asyncio, json, os, sys, time
from collections import defaultdict
from urllib.parse import urlparse
import aiohttp

MAX_AGE_DAYS = int(os.environ.get("MAX_AGE_DAYS", "7"))
GLOBAL = int(os.environ.get("CONCURRENCY", "40"))
PER_HOST = 3
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36 free-dev-roadmaps-linkcheck"
PATH = "data/linkcheck.json"

def now():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

def collect():
    urls = set()
    for f in os.listdir("site/data/r"):
        d = json.load(open(f"site/data/r/{f}"))
        for t in d["topics"]:
            for r in t["resources"]:
                urls.add(r["url"])
                rep = r.get("replacement") or {}
                for k in ("url", "url2", "url3"):
                    if rep.get(k):
                        urls.add(rep[k])
    return sorted(u for u in urls if u.startswith("http"))

async def check(session, url, sems, gsem):
    h = urlparse(url).netloc
    async with gsem, sems[h]:
        rec = {"checked_at": now()}
        for method in ("HEAD", "GET"):
            try:
                async with session.request(method, url, allow_redirects=True, timeout=aiohttp.ClientTimeout(total=25)) as r:
                    code = r.status
                    rec.update(code=code, final_url=str(r.url), method=method)
                    if method == "HEAD" and code in (403, 405, 404, 400, 429, 500, 501):
                        continue  # many servers reject HEAD; retry with GET
                    break
            except aiohttp.ClientConnectorDNSError as e:
                rec.update(code=None, error=f"dns: {e}"); break
            except Exception as e:
                rec.update(code=None, error=f"{type(e).__name__}: {e}"[:200])
                if method == "GET":
                    break
        c = rec.get("code")
        if c is None:
            rec["verdict"] = "broken" if str(rec.get("error", "")).startswith("dns") else "error"
        elif 200 <= c < 400:
            rec["verdict"] = "ok"
        elif c in (404, 410):
            rec["verdict"] = "broken"
        elif c in (401, 403, 429, 451, 999):
            rec["verdict"] = "blocked"
        else:
            rec["verdict"] = "error"
        if rec.get("final_url") == url:
            rec.pop("final_url")
        return url, rec

async def main():
    old = json.load(open(PATH))["results"] if os.path.exists(PATH) else {}
    urls = collect()
    cutoff = time.time() - MAX_AGE_DAYS * 86400
    todo = [u for u in urls if u not in old or time.mktime(time.strptime(old[u]["checked_at"], "%Y-%m-%dT%H:%M:%SZ")) < cutoff
            or old[u].get("verdict") in ("error",)]
    print(f"{len(urls)} unique urls, {len(todo)} to check", flush=True)
    sems = defaultdict(lambda: asyncio.Semaphore(PER_HOST))
    gsem = asyncio.Semaphore(GLOBAL)
    conn = aiohttp.TCPConnector(limit=GLOBAL, ttl_dns_cache=300, ssl=True)
    async with aiohttp.ClientSession(connector=conn, headers={"User-Agent": UA, "Accept": "text/html,application/xhtml+xml,*/*"}) as s:
        done = 0
        for fut in asyncio.as_completed([check(s, u, sems, gsem) for u in todo]):
            u, rec = await fut
            old[u] = rec
            done += 1
            if done % 500 == 0:
                print(done, flush=True)
    results = {u: old[u] for u in urls if u in old}
    summary = defaultdict(int)
    for r in results.values():
        summary[r["verdict"]] += 1
    json.dump({"updated_at": now(), "summary": summary, "results": results}, open(PATH, "w"), indent=0, sort_keys=True)
    print(dict(summary))

asyncio.run(main())
