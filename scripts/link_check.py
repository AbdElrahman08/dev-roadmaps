"""Automated link check for every URL in the inventory.

Verdicts
  ok       final response 2xx/3xx
  broken   404/410 or DNS failure: the page is gone
  blocked  401/403/429/451/999: the site refuses bots; inconclusive, re-check in a browser
  error    timeout, TLS or other network error: inconclusive
Results are incremental: URLs checked within MAX_AGE_DAYS are skipped.
"""
import asyncio, json, os, re, sys, time
from collections import defaultdict
from urllib.parse import urlparse
import aiohttp

MAX_AGE_DAYS = int(os.environ.get("MAX_AGE_DAYS", "7"))
GLOBAL = int(os.environ.get("CONCURRENCY", "40"))
PER_HOST = 3
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36 free-dev-roadmaps-linkcheck"
PATH = "data/linkcheck.json"
FORCE = os.environ.get("FORCE") == "1"
# Text that only appears when a signed-out visitor is blocked from the full content.
PAYWALL_MARKERS = ["member-only story", "this story is only available to medium members", "subscribe to continue reading",
    "subscribe to read", "to continue reading, subscribe", "you've reached your free article limit", "this content is for subscribers only",
    "become a member to read", "unlock this article", "purchase to unlock", "this article is for paid subscribers",
    "sign in to continue reading", "log in to continue reading", "upgrade to premium to unlock", "this lesson is for pro members",
    "enroll to unlock", "buy now to access this course"]
LOGIN_URL_PATTERNS = [r"/(login|signin|sign-in|sign_in|auth|accounts/login)\b", r"accounts\.google\.com", r"login\.microsoftonline", r"[?&]redirect_to=", r"/sso/"]

def now():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

def collect():
    """Every URL the inventory knows about: source resources (shown or removed), replacements and additions."""
    import csv
    urls = set()
    if os.path.exists("data/inventory.csv"):
        for row in csv.DictReader(open("data/inventory.csv")):
            for k in ("url", "replacement_url"):
                if row.get(k): urls.add(row[k])
    for e in json.load(open("data/verifications.json"))["entries"] if os.path.exists("data/verifications.json") else []:
        rep = e.get("replacement") or {}
        for k in ("url", "url2", "url3"):
            if rep.get(k): urls.add(rep[k])
    if os.path.exists("data/additions.json"):
        for a in json.load(open("data/additions.json"))["entries"]:
            urls.add(a["url"])
    return sorted(u for u in urls if u.startswith("http"))

async def check(session, url, sems, gsem):
    h = urlparse(url).netloc
    async with gsem, sems[h]:
        rec = {"checked_at": now()}
        body = b""
        try:
            async with session.get(url, allow_redirects=True, timeout=aiohttp.ClientTimeout(total=30)) as r:
                rec.update(code=r.status, final_url=str(r.url), method="GET")
                ctype = r.headers.get("Content-Type", "")
                if "html" in ctype:
                    body = await r.content.read(400_000)
                rec["content_type"] = ctype.split(";")[0][:60]
        except aiohttp.ClientConnectorDNSError as e:
            rec.update(code=None, error=f"dns: {e}")
        except Exception as e:
            rec.update(code=None, error=f"{type(e).__name__}: {e}"[:200])
        c = rec.get("code")
        # Access check: did the public, signed-out page show a paywall or a login wall?
        if c and 200 <= c < 400:
            fu = rec.get("final_url", url).lower()
            text = body.decode("utf-8", "ignore").lower()
            hits = [m for m in PAYWALL_MARKERS if m in text]
            title = re.search(r"<title[^>]*>(.*?)</title>", text, re.S)
            title = title.group(1).strip()[:120] if title else ""
            if title: rec["title"] = title
            if re.search(r"(page not found|^404\b|\b404 not found|doesn.t exist|wikipedia does not have an article)", title):
                rec["verdict"] = "broken"; rec["soft_404"] = True
            if any(re.search(p, fu) for p in LOGIN_URL_PATTERNS) and not any(re.search(p, url.lower()) for p in LOGIN_URL_PATTERNS):
                rec["access"] = "login wall"
            elif hits:
                rec["access"] = "paywall"; rec["paywall_markers"] = hits[:3]
            else:
                rec["access"] = "open" if (body or "html" not in rec.get("content_type", "html")) else "open (no body read)"
        if rec.get("soft_404"):
            pass
        elif c is None:
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
    todo = urls if FORCE else [u for u in urls if u not in old or time.mktime(time.strptime(old[u]["checked_at"], "%Y-%m-%dT%H:%M:%SZ")) < cutoff
            or old[u].get("verdict") in ("error",) or "access" not in old[u] and old[u].get("verdict") == "ok"]
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
