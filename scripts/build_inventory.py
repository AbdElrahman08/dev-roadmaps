"""Merge roadmap.sh page data + upstream repo content + manual provider verifications + link checks
into one source-of-truth inventory.

Inputs
  upstream/roadmaps/<slug>/content/*.md   (kamranahmedse/developer-roadmap, pinned commit)
  data/pages/<slug>.json                  (roadmap.sh loaded data, from fetch_pages.py)
  data/verifications.json                 (provider-page checks and free replacements, keyed by URL)
  data/linkcheck.json                     (automated link results, keyed by URL; optional)
Outputs
  site/data/index.json, site/data/r/<slug>.json, site/data/search.json
  data/inventory.csv, data/coverage.json
"""
import csv, glob, hashlib, json, os, re, subprocess, sys
from urllib.parse import urlparse

UP = sys.argv[1] if len(sys.argv) > 1 else "upstream"
PAGES = "data/pages"
OUT = "site/data"
os.makedirs(f"{OUT}/r", exist_ok=True)

def git_commit(path):
    try:
        return subprocess.check_output(["git", "-C", path, "rev-parse", "HEAD"], text=True).strip()
    except Exception:
        return "unknown"

REPO_COMMIT = git_commit(UP)
VER = {}
if os.path.exists("data/verifications.json"):
    for v in json.load(open("data/verifications.json"))["entries"]:
        VER[v["url"]] = v
LINKS = json.load(open("data/linkcheck.json"))["results"] if os.path.exists("data/linkcheck.json") else {}

# Hosts whose courses are commonly paywalled or certificate-gated: flagged for provider review, never shown as free until verified.
PAID_HOSTS = {"coursera.org", "udemy.com", "udacity.com", "pluralsight.com", "linkedin.com", "educative.io", "datacamp.com",
              "frontendmasters.com", "oreilly.com", "learning.oreilly.com", "zerotomastery.io", "codecademy.com", "manning.com",
              "amazon.com", "amzn.to", "egghead.io", "scrimba.com", "cbtnuggets.com", "acloudguru.com", "skillshare.com",
              "imp.i384100.net", "edx.org", "maven.com", "teachable.com"}

# Course pages on platforms that commonly paywall or certificate-gate: flagged for provider review, never shown as free until verified.
COURSE_PATHS = {
    "coursera.org": r"^/(learn|specializations?|professional-certificates|projects|programs)/",
    "udemy.com": r"^/course/", "udacity.com": r"^/course", "pluralsight.com": r"^/(courses|paths)/",
    "educative.io": r"^/(courses|path)/", "datacamp.com": r"^/(courses|tracks)/", "frontendmasters.com": r"^/(courses|learn)/",
    "linkedin.com": r"^/learning/", "codecademy.com": r"^/learn/", "zerotomastery.io": r"^/courses/", "egghead.io": r"^/courses/",
    "scrimba.com": r"^/", "edx.org": r"^/(learn|course|certificates|professional-certificate)", "skillshare.com": r"^/",
    "oreilly.com": r"^/(library|videos)/", "learning.oreilly.com": r"^/", "maven.com": r"^/", "acloudguru.com": r"^/", "cbtnuggets.com": r"^/",
}
AFFILIATE_HOSTS = {"imp.i384100.net"}
BOOKSTORES = {"amazon.com", "amzn.to", "manning.com", "oreilly.com"}

ACRONYMS = {"ai":"AI","api":"API","aws":"AWS","css":"CSS","html":"HTML","ios":"iOS","php":"PHP","dba":"DBA","qa":"QA","bi":"BI","sql":"SQL",
            "seo":"SEO","ux":"UX","ui":"UI","mlops":"MLOps","devops":"DevOps","devsecops":"DevSecOps","devrel":"DevRel","graphql":"GraphQL",
            "postgresql":"PostgreSQL","mongodb":"MongoDB","nextjs":"Next.js","nodejs":"Node.js","javascript":"JavaScript","typescript":"TypeScript",
            "aspnet":"ASP.NET","cpp":"C++","github":"GitHub","golang":"Go","leetcode":"LeetCode","wordpress":"WordPress","swift":"Swift","openclaw":"OpenClaw","r":"R","c":"C"}
def nice_title(slug):
    words = [ACRONYMS.get(w, w.capitalize()) for w in slug.split("-")]
    return " ".join(words).replace("Swift UI", "SwiftUI").replace("Ruby On Rails", "Ruby on Rails").replace("Git GitHub", "Git and GitHub").replace("Shell Bash", "Shell / Bash")

def host(u):
    h = (urlparse(u).netloc or "").lower()
    return h[4:] if h.startswith("www.") else h

def rid(*parts):
    return hashlib.sha1("|".join(parts).encode()).hexdigest()[:12]

def node_label(n):
    return ((n.get("data") or {}).get("label") or "").strip()

def classify(url, rtype, in_page_button):
    """Default access status before any manual verification."""
    h = host(url)
    if h.endswith("roadmap.sh"):
        return "internal link", "n/a"
    if url in VER:
        return VER[url]["access_status"], "provider-page"
    path = urlparse(url).path.lower()
    if h in AFFILIATE_HOSTS:
        return "needs provider review", "auto"
    for ph, pat in COURSE_PATHS.items():
        if (h == ph or h.endswith("." + ph)) and re.search(pat, path):
            return "needs provider review", "auto"
    if h in BOOKSTORES:
        return "likely paid (book store)", "auto"
    if rtype == "course":
        return "needs provider review", "auto"
    return "cost not reviewed", "auto"

def parse_repo(slug):
    topics = {}
    for f in sorted(glob.glob(f"{UP}/roadmaps/{slug}/content/*.md")):
        base = os.path.basename(f)[:-3]
        if base == "index":
            continue
        name, tid = base.rsplit("@", 1) if "@" in base else (base, base)
        text = open(f, errors="ignore").read()
        m = re.search(r"^#\s+(.+)$", text, re.M)
        res = [dict(tag=t, title=ti.strip(), url=u.strip()) for t, ti, u in re.findall(r"\[@(\w+)@([^\]]*)\]\(([^)]+)\)", text)]
        if tid in topics:  # the same topic id appears in two files (a renamed topic); merge, dropping repeated URLs
            have = {r["url"] for r in topics[tid]["resources"]}
            topics[tid]["resources"] += [r for r in res if r["url"] not in have]
            topics[tid]["file"] += ", " + base + ".md"
            continue
        topics[tid] = dict(id=tid, label=(m.group(1).strip() if m else name.replace("-", " ").title()), file=base + ".md", resources=res)
    return topics

def parse_page(slug):
    p = f"{PAGES}/{slug}.json"
    if not os.path.exists(p):
        return None
    d = json.load(open(p))
    nodes = d.get("nodes", [])
    def pos(n):
        q = n.get("position") or {}
        return (q.get("y", 0), q.get("x", 0))
    topics = [n for n in nodes if n.get("type") in ("topic", "subtopic") and node_label(n)]
    topics.sort(key=pos)
    buttons = []
    for n in nodes:
        dd = n.get("data") or {}
        href = (dd.get("href") or "").strip()
        if n.get("type") in ("resourceButton", "button") and href:
            buttons.append(dict(id=n["id"], label=node_label(n), url=href, y=pos(n)[0], x=pos(n)[1], type=n["type"]))
        for l in dd.get("links") or []:
            u = (l.get("url") or l.get("href") or "").strip()
            if u:
                buttons.append(dict(id=l.get("id", n["id"]), label=(l.get("label") or "").strip(), url=u, y=pos(n)[0], x=pos(n)[1], type="linksgroup"))
    return dict(title=d.get("title"), updatedAt=d.get("updatedAt"), topics=topics, buttons=buttons, pos=pos)

def link_info(u):
    return LINKS.get(u)

index, search, csv_rows, coverage = [], [], [], []
slugs = sorted(os.listdir(f"{UP}/roadmaps"))
for slug in slugs:
    repo = parse_repo(slug)
    page = parse_page(slug)
    out_topics = []
    order = []
    if page:
        for n in page["topics"]:
            order.append((n["id"], node_label(n), n["type"], page["pos"](n)))
    page_ids = {o[0] for o in order}
    for tid, t in repo.items():
        if tid not in page_ids:
            order.append((tid, t["label"], "topic", (10**9, 0)))
    topic_map = {}
    for i, (tid, label, kind, p) in enumerate(order):
        t = dict(id=tid, label=label, kind=kind, order=i + 1, in_page=tid in page_ids, in_repo=tid in repo, resources=[])
        topic_map[tid] = (t, p)
        out_topics.append(t)
    # repo resources
    for tid, rt in repo.items():
        t = topic_map[tid][0]
        for r in rt["resources"]:
            t["resources"].append(dict(title=r["title"], url=r["url"], type=r["tag"], in_repo=True, in_page=False, page_node_id=""))
    # page buttons: attach to nearest topic above by position (approximate grouping; flagged)
    page_btn = 0
    if page:
        ordered = sorted([(v[1], v[0]) for v in topic_map.values() if v[0]["in_page"]], key=lambda z: z[0])
        extra = None
        for b in page["buttons"]:
            if host(b["url"]).endswith("roadmap.sh"):
                continue
            page_btn += 1
            target = None
            for p_, t in ordered:
                if p_[0] <= b["y"]:
                    target = t
            if target is None:
                if extra is None:
                    extra = dict(id="page-extras", label="Other resources on the page", kind="group", order=len(out_topics) + 1, in_page=True, in_repo=False, resources=[])
                    out_topics.append(extra)
                target = extra
            same = next((r for r in target["resources"] if r["url"] == b["url"]), None)
            if same:
                same["in_page"] = True; same["page_node_id"] = b["id"]
            else:
                target["resources"].append(dict(title=b["label"], url=b["url"], type="page button", in_repo=False, in_page=True,
                                                page_node_id=b["id"], grouping="by page position"))
    # enrich
    counts = dict(resources=0, verified_free=0, uncertain=0, replaced=0, needs_review=0, not_reviewed=0, link_ok=0, link_bad=0, link_unchecked=0)
    for t in out_topics:
        for r in t["resources"]:
            r["id"] = rid(slug, t["id"], r["url"], r["title"])
            st, method = classify(r["url"], r["type"], r["in_page"])
            r["access_status"], r["verification"] = st, method
            v = VER.get(r["url"])
            if v:
                for k in ("cost_evidence", "verified_on", "provider", "level", "prerequisites", "resolved_target", "notes", "action", "replacement"):
                    if v.get(k):
                        r[k] = v[k]
            li = link_info(r["url"])
            if li:
                r["link"] = li
            counts["resources"] += 1
            a = r["access_status"]
            if r.get("action") == "replace":
                counts["replaced"] += 1
            elif a.startswith("free") and method == "provider-page":
                counts["verified_free"] += 1
            elif a == "needs provider review":
                counts["needs_review"] += 1
            elif a in ("cost not reviewed", "internal link"):
                counts["not_reviewed"] += 1
            else:
                counts["uncertain"] += 1
            ls = (li or {}).get("verdict")
            counts["link_ok" if ls == "ok" else "link_bad" if ls in ("broken", "error") else "link_unchecked"] += 1
            search.append([slug, t["label"], r["title"], r["url"], a, r.get("action", "")])
            csv_rows.append(dict(roadmap=slug, topic=t["label"], topic_id=t["id"], title=r["title"], url=r["url"], type=r["type"],
                                 source="+".join(x for x, f in (("page", r["in_page"]), ("repo", r["in_repo"])) if f),
                                 page_node_id=r["page_node_id"], access_status=a, verification=method,
                                 cost_evidence=r.get("cost_evidence", ""), verified_on=r.get("verified_on", ""),
                                 action=r.get("action", ""), replacement_title=(r.get("replacement") or {}).get("title", ""),
                                 replacement_url=(r.get("replacement") or {}).get("url", ""),
                                 replacement_why=(r.get("replacement") or {}).get("why", ""),
                                 link_verdict=(li or {}).get("verdict", "unchecked"), link_code=(li or {}).get("code", ""),
                                 link_checked_at=(li or {}).get("checked_at", "")))
    rec = dict(slug=slug, title=(page or {}).get("title") or nice_title(slug), page_updatedAt=(page or {}).get("updatedAt"),
               page_fetched=bool(page), repo_commit=REPO_COMMIT, topics=out_topics, counts=counts)
    json.dump(rec, open(f"{OUT}/r/{slug}.json", "w"), ensure_ascii=False, separators=(",", ":"))
    index.append(dict(slug=slug, title=rec["title"], page_updatedAt=rec["page_updatedAt"], page_fetched=bool(page),
                      topics=len(out_topics), counts=counts))
    repo_links = sum(len(t["resources"]) for t in repo.values())
    coverage.append(dict(slug=slug, page_fetched=bool(page), page_topics=len(page_ids), repo_topics=len(repo),
                         topics_only_in_page=len(page_ids - set(repo)), topics_only_in_repo=len(set(repo) - page_ids),
                         repo_resource_links=repo_links, page_resource_buttons=page_btn,
                         inventory_resources=counts["resources"]))

totals = {k: sum(i["counts"][k] for i in index) for k in index[0]["counts"]}
json.dump(dict(repo_commit=REPO_COMMIT, roadmaps=index, totals=totals,
               verification_entries=len(VER), linkcheck_entries=len(LINKS)), open(f"{OUT}/index.json", "w"), ensure_ascii=False, indent=1)
json.dump(search, open(f"{OUT}/search.json", "w"), ensure_ascii=False, separators=(",", ":"))
with open("data/inventory.csv", "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(csv_rows[0].keys())); w.writeheader(); w.writerows(csv_rows)
json.dump(dict(repo_commit=REPO_COMMIT, roadmaps=coverage), open("data/coverage.json", "w"), indent=1)
print(json.dumps(totals), f"roadmaps={len(index)} pages_fetched={sum(i['page_fetched'] for i in index)}")
