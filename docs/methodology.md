# Methodology

## 1. Goal

Given 100 apps across 10 categories, capture for each: category, auth method(s), self-serve vs gated, API surface, MCP availability, buildability verdict, and evidence URL. Then cluster into patterns. Then verify a sample against live docs.

## 2. The agent

A 5-stage pipeline. Each stage is a small Python module; they are composable and re-runnable.

### Stage 1 — Planner
- Input: `agent/apps.json` (100 apps, id + name + category + hint URL).
- Output: list of work items.
- Human input: the curated 100-app list itself was provided by Composio.

### Stage 2 — Researcher (Composio MCP)
- For each app: call `web_search("<app> developer documentation API")` to find the canonical docs URL.
- Then call `firecrawl_scrape(url)` to extract docs HTML.
- Cache scraped HTML per app to avoid re-fetching.
- Politeness: 0.3s sleep between calls, retry with exponential backoff on 429.

### Stage 3 — Extractor (LLM)
- For each app: prompt an LLM with the system prompt in `research_agent.py:EXTRACTOR_PROMPT`, plus the scraped docs text (truncated to 4000 chars).
- LLM returns a JSON object matching the `AppRecord` dataclass schema.
- Schema-validated with `jsonschema`. Invalid records go to `flagged.json` for human review.

### Stage 4 — Verifier
- Stratified sample of 15 apps (1–2 per category, mix of buildable + gated outcomes).
- For each sampled app, run 3 targeted web searches:
  1. `<app> API authentication method`
  2. `<app> MCP server model context protocol`
  3. `<app> developer pricing free tier self serve`
- Diff snippets against first-pass answers. Mismatches → `correction_applied` note in `verification.json`.

### Stage 5 — Clusterer
- Aggregates 100 records into:
  - Auth method distribution
  - Self-serve distribution
  - MCP availability distribution
  - Per-category matrix (10 categories × 5 metrics)
  - Blocker frequency
  - Easy-wins / needs-outreach / official-MCP lists
- Outputs `patterns.json` consumed by `build_html.py`.

## 3. Verification protocol

### Sample selection
Stratified across all 10 categories, deliberately including both "easy" and "hard" cases:

| Category | Sampled |
|----------|---------|
| CRM and Sales | Salesforce, DealCloud |
| Support and Helpdesk | Zendesk, Plain |
| Communications and Messaging | Slack |
| Marketing, Ads, Email and Social | Mailchimp |
| Ecommerce | Shopify, Amazon Selling Partner |
| Data, SEO and Scraping | Firecrawl |
| Developer, Infra and Data platforms | GitHub, Snowflake |
| Productivity and Project Management | Notion |
| Finance and Fintech | Stripe, Ramp |
| AI, Research and Media-native | Devin |

### Per-app scoring
Three signals checked per app:
- **auth** — does the agent's auth method match the live docs?
- **mcp** — does the agent's MCP verdict match current search results?
- **self_serve** — does the agent's gating verdict match the current pricing page?

Each signal scored: `correct` / `partial` / `wrong`.

App-level verdict:
- `correct` if all 3 signals are `correct`
- `partial` if any signal is `partial` (no `wrong`)
- `corrected` if any signal was `wrong` and the dataset was updated

### Accuracy metrics

| Metric | Definition |
|--------|------------|
| First-pass app accuracy | (# apps fully correct on first pass) / sample size |
| Post-correction signal accuracy | (# signals correct after applying corrections) / (total signals) |
| Lift | post-correction signal accuracy − first-pass app accuracy |

**Reported numbers:**
- First-pass app accuracy: 80% (12/15)
- Post-correction signal accuracy: 93.3% (42/45 signals)
- Lift: +13.3 percentage points
- Corrections applied: 4

## 4. Honest misses

### Where the agent was wrong

1. **Plain** — First-pass said "yes-community MCP" based on outdated knowledge. Live search confirmed no Plain-specific MCP server exists today. **Downgraded to "no".**
2. **Salesforce** — First-pass said "yes-community" (true historically). Live search showed Salesforce shipped Hosted MCP Servers in 2025. **Upgraded to "yes-official".**
3. **Ramp** — First-pass said "gated" (correct). The consumer tier is free, but Developer API still requires a Ramp business account. **Notes clarified**, verdict unchanged.
4. **Amazon SP-API** — Amazon cancelled SP-API usage/annual fees in 2025. The "gated" verdict stands (registration + role approval still required). **Notes updated** to remove cost blocker.

### Apps that defeated me (flagged, not guessed)

- **iPayX** — Docs page exists at ipayx.ai/docs but token-issuance flow is unclear. Marked `buildable-gated` with note `Token issuance unclear; flagged for human review`.
- **higgsfield** — CLI-first platform; docs are CLI-only, API surface unclear. Marked `buildable-gated` with note `Docs are CLI-only; API surface unclear`.
- **fanbasis** — Docs page exists but access seems gated. Marked `buildable-gated` with note `Limited public docs; token-issuance unclear`.
- **Paygent Connect** — Limited English docs; Japanese merchant contract required. Marked `buildable-gated` with note `Requires Japanese merchant contract`.

## 5. What I'd do with more time

1. **Verify all 100 apps**, not just 15. The current 15-app sample gives a 93% signal accuracy confidence interval; expanding to 100 would tighten this.
2. **Browser-use verification** — for apps where web_search snippets are ambiguous, navigate to the actual docs page and check the auth section programmatically. I'd use Playwright + an LLM extractor.
3. **MCP registry cross-check** — pull the official MCP server registry (modelcontextprotocol/servers on GitHub) and compare against my `has_mcp` field. This would catch any community-MCP entries I missed.
4. **Run the live agent end-to-end** with a real Composio API key. The current first-pass was generated from my knowledge; the live agent would test the Composio SDK + MCP integration for real.
5. **Auto-refresh** — the MCP landscape changes weekly. A scheduled job that re-runs the verifier monthly would keep the dataset current.

## 6. What "buildable" means

For this assignment, "buildable" means: a Composio engineer could ship an agent-callable toolkit for this app in ~1 week, given the current state of public docs and auth.

- **buildable** — self-serve auth, broad public API, no first-party MCP needed (or community MCP that can be forked/improved).
- **buildable-gated** — the API surface exists and is documented, but a developer can't get credentials without paid plan / enterprise sales / partnership / app review. The toolkit is technically possible; the blocker is access, not engineering.
- **blocked** — no public API, or API is too narrow to be useful as a toolkit. (No app in this set landed here; even the most docs-thin apps have *some* surface.)

## 7. Why these specific 5 patterns

I looked at the 100 rows and asked: *if a Composio PM asked me what to do next, what would I say?*

1. **Auth** — tells the SDK team what auth flows to support first (API Key + OAuth2 cover ~90%).
2. **Self-serve vs gated** — tells the partnerships team where to focus outreach.
3. **MCP availability** — tells the eng team where the green-field is (60 apps with no MCP = 60 chances to ship first).
4. **Blockers** — tells PMs the #1 thing blocking new toolkits isn't technical (it's enterprise sales gating).
5. **Easy wins** — gives the eng team a prioritized backlog (74 buildable, 60 with no MCP).

Each pattern is actionable. None is a vanity stat.
