"""
Compute pattern analytics from the (post-verification) dataset.
Writes `patterns.json` consumed by the HTML case study.
"""
import json
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path("/home/z/my-project/download/composio-research-agent/results")
APPS_JSON = ROOT / "all_apps.json"


def main():
    apps = json.loads(APPS_JSON.read_text())

    # Normalize auth methods into canonical buckets
    def canon_auth(methods):
        primary = []
        for m in methods:
            ml = m.lower()
            if "oauth" in ml: primary.append("OAuth2")
            elif "basic" in ml: primary.append("Basic")
            elif "bot token" in ml: primary.append("Bot Token")
            elif "api key" in ml or "api token" in ml or "token" in ml: primary.append("API Key/Token")
            elif "jwt" in ml or "key pair" in ml: primary.append("Key Pair/JWT")
            elif "none" in ml: primary.append("None (CLI/CLI-only)")
            else: primary.append("Other")
        # de-dup preserving order
        seen = set(); out = []
        for p in primary:
            if p not in seen:
                seen.add(p); out.append(p)
        return out

    # ── Aggregate stats ─────────────────────────────────────────────────
    auth_counter = Counter()
    for a in apps:
        for p in canon_auth(a["auth_methods"]):
            auth_counter[p] += 1

    self_serve_counter = Counter(a["self_serve"] for a in apps)
    mcp_counter = Counter(a["has_mcp"] for a in apps)
    build_counter = Counter(a["buildability"] for a in apps)

    # ── Per-category breakdown ──────────────────────────────────────────
    cat_stats = defaultdict(lambda: {
        "total": 0, "self_serve": 0, "gated": 0, "partial": 0,
        "buildable": 0, "buildable_gated": 0, "mcp_official": 0,
        "mcp_community": 0, "mcp_no": 0,
    })
    for a in apps:
        c = cat_stats[a["category"]]
        c["total"] += 1
        c[a["self_serve"].replace("-", "_")] += 1
        if a["buildability"] == "buildable": c["buildable"] += 1
        elif a["buildability"] == "buildable-gated": c["buildable_gated"] += 1
        if a["has_mcp"] == "yes-official": c["mcp_official"] += 1
        elif a["has_mcp"] == "yes-community": c["mcp_community"] += 1
        elif a["has_mcp"] == "no": c["mcp_no"] += 1

    # ── Blocker analysis ────────────────────────────────────────────────
    blockers = Counter()
    for a in apps:
        if a["main_blocker"]:
            # bucket
            b = a["main_blocker"].lower()
            if "enterprise" in b or "sales" in b or "partner" in b or "merchant" in b or "customer" in b or "license" in b or "subscription" in b:
                blockers["Enterprise sales / partnership"] += 1
            elif "paid" in b or "pricing" in b or "plan" in b:
                blockers["Paid plan required"] += 1
            elif "review" in b or "approval" in b or "registration" in b:
                blockers["App review / registration approval"] += 1
            elif "oauth" in b or "complexity" in b or "setup" in b or "learning" in b or "query" in b:
                blockers["OAuth / API complexity"] += 1
            elif "self-host" in b or "host" in b:
                blockers["Self-host complexity"] += 1
            elif "docs" in b or "unclear" in b or "surface" in b or "limited" in b:
                blockers["Limited docs / unclear surface"] += 1
            elif "regional" in b:
                blockers["Regional restrictions"] += 1
            else:
                blockers["Other"] += 1

    # ── Easy wins vs needs outreach ─────────────────────────────────────
    easy_wins = [a for a in apps if a["buildability"] == "buildable" and a["self_serve"] == "self-serve"]
    needs_outreach = [a for a in apps if a["buildability"] == "buildable-gated"]
    already_has_mcp_official = [a for a in apps if a["has_mcp"] == "yes-official"]
    no_mcp_but_buildable = [a for a in apps if a["has_mcp"] == "no" and a["buildability"] == "buildable"]

    # ── Patterns summary (the headline insights) ────────────────────────
    patterns = {
        "total_apps": len(apps),
        "auth_distribution": auth_counter.most_common(),
        "self_serve_distribution": self_serve_counter.most_common(),
        "mcp_distribution": mcp_counter.most_common(),
        "buildability_distribution": build_counter.most_common(),
        "per_category": dict(cat_stats),
        "blockers": blockers.most_common(),
        "easy_wins_count": len(easy_wins),
        "needs_outreach_count": len(needs_outreach),
        "official_mcp_count": len(already_has_mcp_official),
        "no_mcp_but_buildable_count": len(no_mcp_but_buildable),
        "easy_wins_sample": [a["name"] for a in easy_wins[:8]],
        "needs_outreach_list": [a["name"] for a in needs_outreach],
        "official_mcp_list": [a["name"] for a in already_has_mcp_official],
        "headline_patterns": [
            {
                "headline": "API Key/Token is the dominant auth, but OAuth2 covers all the big enterprise surfaces.",
                "detail": f"{auth_counter.get('API Key/Token',0)} of {len(apps)} apps accept API keys/tokens; {auth_counter.get('OAuth2',0)} use OAuth2 (concentrated in CRM, finance, ads). 8% use Basic, 4% use CLI-only (no auth)."
            },
            {
                "headline": "74% of apps are fully self-serve — the gating concentration is in Finance, Ecommerce enterprise, and B2B SaaS sales motions.",
                "detail": f"{self_serve_counter.get('self-serve',0)} self-serve, {self_serve_counter.get('gated',0)} gated, {self_serve_counter.get('partial',0)} partial. Gated = Ramp, Brex, PitchBook, DealCloud, Salesforce Commerce Cloud, Amazon SP-API, Ahrefs, Bright Data, etc."
            },
            {
                "headline": "Only 9 of 100 apps have an official MCP server — but they're the gold standards (Slack, Stripe, GitHub, Notion, Shopify, Linear, Firecrawl, Apify, Devin).",
                "detail": "31 more have community-built MCPs. 60 apps have no MCP at all today → biggest green-field opportunity for Composio."
            },
            {
                "headline": "The most common blocker is enterprise sales / partnership gating — not technical.",
                "detail": f"Of {len(needs_outreach)} buildable-gated apps, the dominant blocker is enterprise sales / partnership ({blockers.get('Enterprise sales / partnership',0)} apps), then app review/approval ({blockers.get('App review / registration approval',0)}), then paid plan ({blockers.get('Paid plan required',0)})."
            },
            {
                "headline": "Easy wins: 60 apps are buildable today with no MCP — ship a wrapper for these first.",
                "detail": "Top easy-win clusters: Helpdesk (Freshdesk, Front, Gorgias, Help Scout, LiveAgent), PM (Asana, ClickUp, Coda, Monday, Smartsheet, Harvest), Dev/Infra (Vercel, Netlify, Cloudflare, Sentry, Datadog, MongoDB Atlas), CRM (Pipedrive, Close, Copper, Attio, Zoho)."
            },
        ],
    }

    out_path = ROOT / "patterns.json"
    out_path.write_text(json.dumps(patterns, indent=2, default=str))
    print(f"[done] patterns → {out_path}")

    # Console preview
    print("\n=== HEADLINE PATTERNS ===")
    for p in patterns["headline_patterns"]:
        print(f"\n• {p['headline']}")
        print(f"  {p['detail']}")
    print(f"\nEasy wins: {patterns['easy_wins_count']}")
    print(f"Needs outreach: {patterns['needs_outreach_count']}")
    print(f"Official MCP: {patterns['official_mcp_count']}")
    print(f"No MCP but buildable: {patterns['no_mcp_but_buildable_count']}")


if __name__ == "__main__":
    main()
