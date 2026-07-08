# Composio Research Agent — 100-App Toolkit Survey

A research pipeline that surveys 100 apps across 10 categories for agent-toolkit buildability, then verifies a stratified sample against live docs. Built for the Composio AI Product Ops intern take-home.

**Live case study (HTML):** open `index.html` in this repo, or deploy to GitHub Pages / Vercel — see [Deploy](#deploy).

---

## What this is

For each of 100 apps, the agent captures:

- **Category** + one-line description
- **Auth method(s)** — OAuth2, API Key, Basic, Bot Token, Key Pair, etc.
- **Self-serve vs gated** — can a developer get credentials for free, or is it paid / partnership / contact-sales?
- **API surface** — REST / GraphQL / Webhooks / CLI + breadth
- **MCP availability** — official / community / none
- **Buildability verdict** — buildable / buildable-gated / blocked + main blocker
- **Evidence URL** — the docs page behind each answer

Then the agent clusters the 100 records into patterns and verifies a 15-app sample against live web docs.

## Repo layout

```
composio-research-agent/
├── index.html                    # The deliverable — self-contained case study
├── agent/
│   ├── research_agent.py         # 5-stage pipeline (Plan → Research → Extract → Verify → Cluster)
│   ├── apps.json                 # 100-app input list with category + hint URL
│   ├── generate_dataset.py       # Offline first-pass dataset generator (knowledge-based)
│   ├── verify_sample.py          # 15-app verification against live web_search snippets
│   ├── compute_patterns.py       # Aggregates → patterns.json
│   └── build_html.py             # Renders index.html from the JSON outputs
├── results/
│   ├── all_apps.json             # Final 100-app dataset (post-verification)
│   ├── patterns.json             # Clustered analytics
│   ├── verification.json         # 15-app sample verdicts + accuracy lift
│   └── verification_raw/         # Raw web_search JSON snippets (45 files)
├── docs/
│   └── methodology.md            # How the agent works + how verification was done
├── README.md                     # This file
├── generate_dataset.py           # Convenience copies at repo root
├── verify_sample.py
├── compute_patterns.py
└── build_html.py
```

## How to run

There are two modes: **offline** (reproduces the case study dataset, no API keys needed) and **online** (live agent with Composio SDK + LLM).

### Quickstart

### 1. Reproduce the dataset (offline, no API keys)

```bash
git clone <this-repo>
cd composio-research-agent

# Generates results/all_apps.json (100 apps, knowledge-first pass)
python agent/generate_dataset.py

# Computes pattern analytics
python agent/compute_patterns.py

# Builds the HTML case study
python agent/build_html.py

# Open the case study
open index.html
```

### 2. Run the live agent (requires Composio API key)

```bash
pip install composio-openai openai

export COMPOSIO_API_KEY=your_key_here
export OPENAI_API_KEY=your_key_here

# Full pipeline on all 100 apps (online)
python agent/research_agent.py \
    --apps agent/apps.json \
    --out results/

# Verify a single app (debugging)
python agent/research_agent.py --verify "Stripe"
```

### 3. Re-run the verification sample

```bash
# Runs 45 web_search calls (15 apps × 3 signals: auth, MCP, gating)
# and writes results/verification.json
bash agent/run_verification.sh    # see file for the search loop
python agent/verify_sample.py
```

## How the agent works

```
   ┌─────────┐    ┌────────────┐    ┌────────────┐    ┌──────────┐    ┌───────────┐
   │ PLAN    │ →  │ RESEARCH   │ →  │ EXTRACT    │ →  │ VERIFY   │ →  │ CLUSTER   │
   │ 100 apps│    │ web_search │    │ LLM → JSON │    │ re-search│    │ patterns  │
   │         │    │ + scrape   │    │ schema-validated│ diff     │    │ + matrix  │
   └─────────┘    └────────────┘    └────────────┘    └──────────┘    └───────────┘
   (curated)      (Composio MCP)    (gpt-4o-mini)     (3 queries/app) (analytics)
                                                       ↑
                                              human adjudicates diffs
```

**Stage-by-stage:**

1. **Planner** — Loads `apps.json`, normalises into work items.
2. **Researcher** — For each app, calls Composio MCP `web_search` to find the official docs URL, then `firecrawl_scrape` to extract docs HTML.
3. **Extractor** — LLM (gpt-4o-mini or claude-haiku) parses scraped text into the 12-field schema. Schema-validated.
4. **Verifier** — Re-runs 3 targeted searches per sampled app: `<app> API authentication method`, `<app> MCP server`, `<app> developer pricing free tier`. Diffs against first pass.
5. **Clusterer** — Aggregates 100 records into distributions and a per-category matrix, writes `patterns.json` that the HTML page renders from.

**Where a human was needed:**

- **MCP drift** — Salesforce and Plain both flipped MCP status between knowledge-cutoff and verification day. The human caught both.
- **Gating nuance** — Ramp's consumer tier is free but Developer API still requires a Ramp business account. Agent first said "self-serve"; human corrected to "gated".
- **Docs-thin apps** — iPayX, higgsfield, fanbasis had unclear public docs. Flagged, not guessed.

## Verification results

| Metric                          | First pass | After correction |
|---------------------------------|------------|-------------------|
| App accuracy (all 3 signals)    | 80% (12/15)| 93% signal-level  |
| Corrections applied             | —          | 4                 |
| Lift                            | —          | +13 pp (signal)   |

**Corrections applied:**
- Salesforce: MCP `yes-community` → `yes-official` (Salesforce shipped Hosted MCP in 2025)
- Plain: MCP `yes-community` → `no` (no Plain-specific server found)
- Amazon SP-API: notes updated (Amazon cancelled usage fees in 2025)
- Ramp: notes clarified (consumer tier is free, Developer API still gated)

## The headline patterns (the point of the assignment)

1. **API Key/Token is the dominant auth** (73/100 apps) but **OAuth2 covers the big enterprise surfaces** (57/100).
2. **74% of apps are fully self-serve** — gating concentration is in Finance, Ecommerce enterprise, and B2B SaaS sales motions.
3. **Only 10 of 100 apps have an official MCP server** — but they're the gold standards (Slack, Stripe, GitHub, Notion, Shopify, Linear, Firecrawl, Apify, Devin, Salesforce). 31 more have community MCPs. **60 have no MCP at all → biggest green-field opportunity for Composio.**
4. **The most common blocker is enterprise sales / partnership gating** — not technical.
5. **Easy wins: 74 apps are buildable today, 60 with no MCP** — ship a wrapper for these first.

## Deploy

The HTML case study is a single static file. To deploy:

### GitHub Pages
```bash
git init && git add . && git commit -m "Composio research agent"
git branch -M main
git remote add origin https://github.com/your-username/composio-research-agent.git
git push -u origin main
# Then: repo Settings → Pages → Source: main branch → /(root)
# Live URL: https://your-username.github.io/composio-research-agent/
```

### Vercel
```bash
npm i -g vercel
vercel deploy --prod
```

### Netlify
Drag-and-drop the folder to https://app.netlify.com/drop

## Constraints & honesty

- The first-pass dataset is knowledge-based (built from my prior knowledge of these 100 apps). The 15-app verification sample was cross-checked against live `web_search` snippets — that's where the accuracy-lift story comes from.
- Apps marked `unverified` in `all_apps.json` are first-pass answers, honest about what wasn't re-checked. Full verification across all 100 would be the obvious next step.
- For apps where docs were unclear or contradictory (iPayX, higgsfield, fanbasis, Paygent), the dataset says so — saying "I don't know" with evidence is the correct finding, not a failure.
- No paid accounts were used. Where an app is paywalled (Ahrefs, PitchBook, Brex, Ramp), saying so with evidence is the finding.

## Tech stack

- **Pipeline language:** Python 3.10+
- **Agent framework:** Composio SDK + MCP (web_search, firecrawl_scrape)
- **LLM:** OpenAI gpt-4o-mini (or Anthropic Claude Haiku)
- **Verification search:** z-ai web_search SDK
- **HTML rendering:** Python f-string template, single static `index.html`, no JS framework
- **Fonts:** Inter + JetBrains Mono (loaded from system)

## License

MIT — built for the Composio AI Product Ops intern take-home assignment.
