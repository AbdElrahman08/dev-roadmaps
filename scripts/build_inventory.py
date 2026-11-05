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
ADD = {}
if os.path.exists("data/additions.json"):
    for a in json.load(open("data/additions.json"))["entries"]:
        ADD.setdefault((a["roadmap"], a["topic_id"]), []).append(a)

def link_open(li):
    """Verified open access: page loaded (2xx/3xx) for a signed-out visitor with no paywall or login wall detected."""
    if not li or li.get("verdict") != "ok":
        return False
    return li.get("access", "open").startswith("open")

def hard_fail(li):
    """A definite failure: the page is gone or walled. Bot blocks and timeouts are inconclusive, not failures."""
    return bool(li) and (li.get("verdict") == "broken" or li.get("access") in ("paywall", "login wall"))

def verdict(r):
    """Return (verified, basis_or_reason)."""
    li = r.get("link"); a = r["access_status"]
    if r.get("action") == "replace" and r.get("replacement"):
        rl = LINKS.get(r["replacement"]["url"])
        if hard_fail(rl):
            return False, "replacement link broken or walled"
        return True, "free replacement (provider page checked)"
    if r.get("source") == "added":
        if not link_open(li):
            return False, "added resource not yet confirmed by the link and paywall check"
        return True, "added for an empty topic: relevance reviewed by hand, open access confirmed by the link check"
    if r["verification"] == "provider-page" and a.startswith("free") and not hard_fail(li):
        return True, "provider page checked by hand"
    if not li:
        return False, "link not checked yet"
    if li.get("verdict") != "ok":
        return False, f"link {li.get('verdict')}" + (f" ({li.get('code')})" if li.get("code") else "")
    if not link_open(li):
        return False, li.get("access", "access not open")
    if r["verification"] == "provider-page":
        return (True, "provider page checked") if a.startswith("free") else (False, a)
    if a == "cost not reviewed":
        return True, "open-access check: loaded publicly, no paywall or login wall"
    return False, a

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
    "scrimba.com": r"^/(?!articles|blog)", "edx.org": r"^/(learn|course|certificates|professional-certificate)", "skillshare.com": r"^/",
    "oreilly.com": r"^/(library|videos|live-events)/", "learning.oreilly.com": r"^/", "maven.com": r"^/", "acloudguru.com": r"^/(course|learning-paths?)", "cbtnuggets.com": r"^/(it-training|learn|training)/",
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
    if h.endswith("roadmap.sh") or url.startswith("/"):
        return "internal link", "n/a"
    if re.search(r"linkedin\.com/in/|utm_source=roadmap|[?&]c=img-|discord\.gg/", url) or (h == "github.com" and len([x for x in urlparse(url).path.split("/") if x]) == 1) or (in_page_button and rtype == "page button" and re.search(r"Visit (his|her|their) |Profile|Website$", "")):
        return "sponsor or profile link", "auto"
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
    t = d.get("title")
    if isinstance(t, dict): t = t.get("page") or t.get("card")
    return dict(title=t, ai_courses=len(d.get("aiCourses") or []), partner=bool(d.get("partner")), updatedAt=d.get("updatedAt"), topics=topics, buttons=buttons, pos=pos)

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
            if host(b["url"]).endswith("roadmap.sh") or b["url"].startswith("/") or b["url"].startswith("#"):
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
    # reviewed additions for topics that had no verified link
    for t in out_topics:
        for a in ADD.get((slug, t["id"]), []):
            t["resources"].append(dict(title=a["title"], url=a["url"], type=a.get("type", "article"), in_repo=False, in_page=False,
                                       page_node_id="", source="added", provider=a.get("provider", ""), cost_evidence=a.get("evidence", ""),
                                       why=a.get("why", ""), verified_on=a.get("verified_on", "")))
    # enrich
    counts = dict(resources=0, shown=0, removed=0, added=0, verified_free=0, uncertain=0, replaced=0, needs_review=0, not_reviewed=0, link_ok=0, link_bad=0, link_unchecked=0)
    for t in out_topics:
        for r in t["resources"]:
            r["id"] = rid(slug, t["id"], r["url"], r["title"])
            st, method = classify(r["url"], r["type"], r["in_page"])
            if r.get("source") == "added":
                st, method = "free", "provider-page"
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
            ok, why = verdict(r)
            r["verified"], r["basis" if ok else "removed_reason"] = ok, why
            counts["shown" if ok else "removed"] += 1
            if r.get("source") == "added": counts["added"] += 1
            a = r["access_status"]
            if r.get("action") == "replace":
                counts["replaced"] += 1
            elif a.startswith("free") and method == "provider-page":
                counts["verified_free"] += 1
            elif a == "needs provider review":
                counts["needs_review"] += 1
            elif a in ("cost not reviewed", "internal link", "sponsor or profile link"):
                counts["not_reviewed"] += 1
            else:
                counts["uncertain"] += 1
            ls = (li or {}).get("verdict")
            counts["link_ok" if ls == "ok" else "link_bad" if ls in ("broken", "error") else "link_unchecked"] += 1
            if ok:
                search.append([slug, t["label"], (r.get("replacement") or {}).get("title") or r["title"], (r.get("replacement") or {}).get("url") or r["url"], a, r.get("action", "")])
            csv_rows.append(dict(roadmap=slug, topic=t["label"], topic_id=t["id"], title=r["title"], url=r["url"], type=r["type"],
                                 source="+".join(x for x, f in (("page", r["in_page"]), ("repo", r["in_repo"]), ("added", r.get("source") == "added")) if f),
                                 page_node_id=r["page_node_id"], access_status=a, verification=method,
                                 cost_evidence=r.get("cost_evidence", ""), verified_on=r.get("verified_on", ""),
                                 action=r.get("action", ""), replacement_title=(r.get("replacement") or {}).get("title", ""),
                                 replacement_url=(r.get("replacement") or {}).get("url", ""),
                                 replacement_why=(r.get("replacement") or {}).get("why", ""),
                                 link_verdict=(li or {}).get("verdict", "unchecked"), link_code=(li or {}).get("code", ""),
                                 link_checked_at=(li or {}).get("checked_at", ""), link_access=(li or {}).get("access", ""),
                                 shown_on_site="yes" if ok else "no", basis_or_removed_reason=why,
                                 added_source="added" if r.get("source") == "added" else ""))
    site_topics = []
    for t in out_topics:
        keep = [r for r in t["resources"] if r["verified"]]
        if t["id"] == "page-extras" and not keep:
            continue
        site_topics.append(dict(t, resources=keep, removed=len(t["resources"]) - len(keep)))
    counts["topics_without_verified_link"] = sum(1 for t in site_topics if not t["resources"])
    rec = dict(slug=slug, title=(page or {}).get("title") or nice_title(slug), page_updatedAt=(page or {}).get("updatedAt"),
               page_fetched=bool(page), repo_commit=REPO_COMMIT, topics=site_topics, counts=counts)
    json.dump(rec, open(f"{OUT}/r/{slug}.json", "w"), ensure_ascii=False, separators=(",", ":"))
    index.append(dict(slug=slug, title=rec["title"], page_updatedAt=rec["page_updatedAt"], page_fetched=bool(page),
                      topics=len(out_topics), counts=counts))
    repo_links = sum(len(t["resources"]) for t in repo.values())
    coverage.append(dict(slug=slug, page_fetched=bool(page), page_ai_course_titles_without_links=(page or {}).get("ai_courses", 0), page_partner_promo=(page or {}).get("partner", False), page_topics=len(page_ids), repo_topics=len(repo),
                         topics_only_in_page=len(page_ids - set(repo)), topics_only_in_repo=len(set(repo) - page_ids),
                         repo_resource_links=repo_links, page_resource_buttons=page_btn,
                         inventory_resources=counts["resources"]))

totals = {k: sum(i["counts"].get(k, 0) for i in index) for k in index[0]["counts"]}
json.dump(dict(repo_commit=REPO_COMMIT, roadmaps=index, totals=totals,
               verification_entries=len(VER), linkcheck_entries=len(LINKS)), open(f"{OUT}/index.json", "w"), ensure_ascii=False, indent=1)
json.dump(search, open(f"{OUT}/search.json", "w"), ensure_ascii=False, separators=(",", ":"))
with open("data/inventory.csv", "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(csv_rows[0].keys())); w.writeheader(); w.writerows(csv_rows)
json.dump(dict(repo_commit=REPO_COMMIT, roadmaps=coverage), open("data/coverage.json", "w"), indent=1)
print(json.dumps(totals), f"roadmaps={len(index)} pages_fetched={sum(i['page_fetched'] for i in index)}")
