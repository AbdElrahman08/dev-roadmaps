# Free Dev Roadmaps

Every [roadmap.sh](https://roadmap.sh/) roadmap rebuilt from **one source-of-truth inventory**, with:

- **Provider-page cost checks** for every course and paid/affiliate link (`data/verifications.json`): access status, quoted evidence, verification date.
- **Free replacements** for paid or access-uncertain courses, each with why it matches and what it leaves out.
- **Uncertainty labels**: anything whose free access could not be confirmed is never shown as free.
- **Weekly automated link checks** (`data/linkcheck.json`) and a coverage report against the source (`data/coverage.json`).

Independent study aid with its own design; not affiliated with roadmap.sh. Content is derived from
[kamranahmedse/developer-roadmap](https://github.com/kamranahmedse/developer-roadmap) and roadmap.sh's public page data.

## How it works

| Step | Script | Output |
|---|---|---|
| Fetch live page data for every roadmap | `scripts/fetch_pages.py` | `data/pages/<slug>.json` |
| Merge page data + repo content + verifications + link results | `scripts/build_inventory.py` | `site/data/**`, `data/inventory.csv`, `data/coverage.json` |
| Check every URL | `scripts/link_check.py` | `data/linkcheck.json` |
| Browser tests (search, filters, navigation, saved progress) | `scripts/test_site.js` | console report |

`.github/workflows/build.yml` runs the whole pipeline on every change to `data/verifications.json`, weekly, and on demand, then deploys `site/` to GitHub Pages.

## Status labels

| Label | Meaning |
|---|---|
| FREE | Free access confirmed on the provider's own page (evidence quoted) |
| FREE · TIME-LIMITED | Provider says it is free now but only temporarily |
| FREE REPLACEMENT | Original was paid/uncertain; replaced by a verified free equivalent |
| UNCERTAIN / PAID | Free access not confirmed, or paid with no verified replacement yet |
| NOT REVIEWED | Link checked automatically; cost not yet reviewed by hand |
| BROKEN LINK | Link check returned 404/410 or DNS failure |

No independent human curriculum review has been done; replacement rationales are machine-assisted judgements.
