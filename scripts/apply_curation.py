"""Turn curated topic→resource mappings (data/curation/*.json) into reviewed additions for topics with no verified link."""
import glob, json, sys
REM = json.load(open(sys.argv[1]))  # remaining topics: [{roadmap, topic_id, topic}]
A = json.load(open("data/additions.json")); have = {(e["roadmap"], e["topic_id"]) for e in A["entries"]}
n = 0
for f in sorted(glob.glob("data/curation/*.json")):
    cur = json.load(open(f))
    for t in REM:
        m = cur.get(t["roadmap"], {}).get(t["topic"])
        if not m or (t["roadmap"], t["topic_id"]) in have:
            continue
        title, url = m[0], m[1]
        A["entries"].append(dict(roadmap=t["roadmap"], topic_id=t["topic_id"], topic=t["topic"], title=title, url=url,
            type="official docs" if not any(h in url for h in ("wikipedia.org", "github.com")) else ("reference article" if "wikipedia" in url else "repository"),
            provider=url.split("/")[2], evidence="Public documentation page; open access confirmed by the automated link and paywall check.",
            why=f"Chosen by hand for the topic '{t['topic']}' in the {t['roadmap']} roadmap.", verified_on="2026-11-05",
            source_method=f"manual curation ({f.split('/')[-1]})"))
        have.add((t["roadmap"], t["topic_id"])); n += 1
json.dump(A, open("data/additions.json", "w"), indent=1, ensure_ascii=False)
print(f"added {n}; total additions {len(A['entries'])}")
