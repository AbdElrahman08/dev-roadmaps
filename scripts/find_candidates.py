"""For every roadmap topic with no verified link, collect candidate resources for human review.

Sources: Wikipedia search (query = topic label + roadmap context). Results go to data/candidates.json;
nothing is added to the roadmap until a reviewer accepts it in data/additions.json.
"""
import json, time, urllib.parse, urllib.request

UA = "dev-roadmaps candidate finder (https://github.com/AbdElrahman08/dev-roadmaps)"
CONTEXT = {
 "engineering-manager": "engineering management", "seo": "search engine optimization", "design-system": "design system user interface",
 "devrel": "developer relations", "technical-writer": "technical writing", "bi-analyst": "business intelligence",
 "datastructures-and-algorithms": "algorithm data structure", "ux-design": "user experience design", "cpp": "C++",
 "power-bi": "Microsoft Power BI", "data-engineer": "data engineering", "ruby-on-rails": "Ruby on Rails", "leetcode": "algorithm",
 "ios": "iOS development", "qa": "software testing", "scala": "Scala programming", "machine-learning": "machine learning",
 "product-design": "product design", "software-design-architecture": "software architecture", "redis": "Redis",
 "software-architect": "software architecture", "game-developer": "game development", "aspnet-core": "ASP.NET Core", "sql": "SQL",
 "devsecops": "DevSecOps security", "c": "C programming language", "system-design": "distributed systems", "full-stack": "web development",
 "wordpress": "WordPress", "shell-bash": "Bash shell", "postgresql-dba": "PostgreSQL", "typescript": "TypeScript", "laravel": "Laravel",
 "data-analyst": "data analysis", "cyber-security": "computer security", "ai-product-builder": "artificial intelligence product",
 "ai-engineer": "large language model", "nodejs": "Node.js", "network-engineer": "computer networking", "computer-science": "computer science",
 "javascript": "JavaScript", "java": "Java programming", "inference-engineering": "machine learning inference", "terraform": "Terraform",
 "swift-ui": "SwiftUI", "python-data-analysis": "Python data analysis", "php": "PHP", "forward-deployed-engineer": "software engineering",
 "code-review": "code review", "claude-code": "Claude Code", "angular": "Angular", "android": "Android development",
}
def ctx(slug):
    return CONTEXT.get(slug, slug.replace("-", " "))

def wiki(q):
    url = "https://en.wikipedia.org/w/api.php?" + urllib.parse.urlencode(dict(action="query", list="search", srsearch=q, srlimit=3, format="json", srprop="snippet"))
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=20) as r:
                d = json.load(r)
            return [dict(title=x["title"], url="https://en.wikipedia.org/wiki/" + urllib.parse.quote(x["title"].replace(" ", "_")),
                         snippet=x["snippet"].replace('<span class="searchmatch">', "").replace("</span>", "")[:200]) for x in d["query"]["search"]]
        except Exception as e:
            time.sleep(2 + attempt * 3)
    return []

out = []
for line in open("data/empty_topics.tsv"):
    slug, tid, label, kind = line.rstrip("\n").split("\t")
    q = f"{label} {ctx(slug)}"
    out.append(dict(roadmap=slug, topic_id=tid, topic=label, kind=kind, query=q, wikipedia=wiki(q)))
    time.sleep(0.2)
json.dump(dict(generated=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), topics=out), open("data/candidates.json", "w"), indent=1, ensure_ascii=False)
print(len(out), "topics;", sum(1 for o in out if o["wikipedia"]), "with candidates")
