# Research workspace — dev-roadmaps as a business

Stage 1 closed 2026-11-05. The registers in this folder are the source of truth, and the Sheets artifact mirrors them.

## Completed investigations
- Connector inventory (see "Tool limitations" below).
- Upstream licence check (EV-001).
- Competitor pricing taken from the official pages of 8 competitors (EV-002 to EV-009). Scrimba is still unverified.
- Free training at scale in Egypt (EV-010, EV-011).

## New evidence
12 records in `market_evidence.csv`, each with its source URL and the date accessed.

## Unresolved questions
- Will the roadmap.sh author consent to reuse, and on what terms? (RK-001)
- How much demand is there? No interviews, survey responses or usage data exist yet. (RK-005)
- Individual roadmap.sh Pro prices and Scrimba prices were not shown on their pages.
- Do Egypt's government programmes charge learners anything? The official DEPI site failed to load.
- TAM, SAM, SOM, CAC and churn are all UNKNOWN. None of them has been estimated.

## Rejected hypotheses
- "The roadmap.sh content can be republished freely." The licence contradicts this (EV-001).

## Updated assumptions
The only values recorded are competitor list prices (FA-004 to FA-006). Every other financial input stays UNKNOWN.

## Decisions
- D-001 decided on 6 Nov 2026: rebuild independently. The public site, Darb, is in `web/` and uses original paths and courses taken directly from the providers. The data derived from roadmap.sh stays private.
- D-004 decided on 6 Nov 2026: v1 includes a cohort waitlist, sponsor slots, an institution plan and donations. No prices will be published until they've been tested.
- D-002 and D-003 are still proposed.

## Next research priorities
1. Connect the Darb forms (Typeform, created only with your approval) and a donation link, then put the `web/` folder in its own public repository.
2. VE-001: learner interviews and a Typeform survey. The survey is published only with your approval.
3. VE-002: interviews with institutions, tracked in HubSpot. CRM records are created only with your approval.
4. Size the market (FA-001 to FA-003) from primary statistics.

## Tool limitations (stage 1)
| Needed | Status | Fallback used |
|---|---|---|
| Semrush | Connected, but the account has no API units left | None. SEO and traffic data was not obtained |
| Ahrefs, Similarweb | Not connected | None. Traffic estimates were not obtained |
| Google Trends | No connector | Not obtained (manual check possible in a browser) |
| G2, Trustpilot, Product Hunt | No connector | Not used in stage 1 |
| Google Drive, Google Sheets | Not connected | GitHub CSV files plus a Claude Sheets artifact |
| Notion | Account allows databases, but the create tools are not loaded in this session | GitHub CSV files, ready to import |
| Typeform, HubSpot, Figma | Connected | Not used yet (each needs your approval to create or publish anything) |
| Linear | Not connected | Not needed yet |
| GitHub API for other repos | Blocked for repositories outside this session | Used the roadmap.sh self-reported figures, labelled as self-reported |
