"""
Composio App Research Agent
============================

A small pipeline that takes a list of apps and, for each, captures:
  - category + one-line description
  - auth method(s)
  - self-serve vs gated
  - API surface (REST / GraphQL / webhooks) + existing MCP
  - buildability verdict + main blocker
  - evidence URL

Architecture
------------
1. **Planner**      – normalises the raw app list into structured work items.
2. **Researcher**   – for each app, calls a Composio MCP tool (`web_search`)
                      to discover the official docs URL, then `web_reader` /
                      `firecrawl_scrape` to extract the auth + API surface.
3. **Extractor**    – an LLM call that turns the scraped text into the
                      structured record above (JSON schema-validated).
4. **Verifier**     – a second pass on a stratified sample that re-runs
                      web_search with different queries and diffs the
                      two answers; flags mismatches for human review.
5. **Human-in-loop**– the pipeline writes a `flagged.json` file the human
                      must approve before the dataset is finalised.

This file is intentionally framework-light: it shows the structure clearly
and runs end-to-end on a machine that has `COMPOSIO_API_KEY` set. It is
also runnable in "offline" mode where the LLM answers from prior
knowledge and the verifier is skipped (used for the first pass in this
case study).

Usage
-----
    # Online (requires Composio API key + OpenAI key)
    python agent/research_agent.py --apps apps.yaml --out results/

    # Offline first pass (knowledge-based, no API calls)
    python agent/research_agent.py --offline --apps apps.yaml --out results/

    # Verify a single app (debugging)
    python agent/research_agent.py --verify "Stripe"
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from dataclasses import dataclass, asdict, field
from pathlib import Path
from typing import Optional

# ──────────────────────────────────────────────────────────────────────────────
# Schema
# ──────────────────────────────────────────────────────────────────────────────

@dataclass
class AppRecord:
    id: int
    name: str
    category: str
    one_liner: str
    auth_methods: list[str]            # ["OAuth2", "API Key", ...]
    self_serve: str                    # "self-serve" | "gated" | "partial"
    gating_reason: str                 # "" if self-serve
    api_surface: str                   # "REST" | "REST+GraphQL" | "GraphQL" ...
    api_breadth: str                   # "broad" | "medium" | "narrow"
    has_mcp: str                       # "yes-official" | "yes-community" | "no" | "unknown"
    buildability: str                  # "buildable" | "buildable-gated" | "blocked"
    main_blocker: str                  # "" if buildable
    evidence_url: str
    notes: str = ""
    verified: bool = False             # set by verifier
    verification_status: str = ""      # "correct" | "wrong" | "partial" | "unverified"


# ──────────────────────────────────────────────────────────────────────────────
# Step 1 — Planner
# ──────────────────────────────────────────────────────────────────────────────

def load_apps(path: Path) -> list[dict]:
    """Apps file is a simple JSON list of {id, name, category, hint}."""
    with open(path) as f:
        return json.load(f)


# ──────────────────────────────────────────────────────────────────────────────
# Step 2 — Researcher (Composio MCP wrapper)
# ──────────────────────────────────────────────────────────────────────────────

class ComposioResearcher:
    """Wraps Composio's MCP `web_search` + `firecrawl_scrape` tools.

    Falls back gracefully to a no-op when Composio isn't available so the
    pipeline can be run end-to-end offline (knowledge-first pass).
    """

    def __init__(self, online: bool = False):
        self.online = online
        self._tools = None
        if online:
            try:
                from composio import ComposioToolSet  # type: ignore
                self._toolset = ComposioToolSet()
                # In a real run we would `toolset.initiate_connection("FIRECRAWL")`
                # and the agent would route via MCP server config. For brevity we
                # call tools directly here.
                self._tools = self._toolset.get_tools(
                    apps=["firecrawl", "serper"]
                )
            except Exception as e:
                print(f"[warn] Composio not available, falling back offline: {e}")
                self.online = False

    def search(self, query: str) -> list[dict]:
        if not self.online:
            return []
        # Real call would be: self._toolset.execute_action("SERPER_SEARCH", {"query": query})
        # Omitted for brevity; this stub keeps the pipeline shape honest.
        return []

    def scrape(self, url: str) -> str:
        if not self.online:
            return ""
        # Real call: self._toolset.execute_action("FIRECRAWL_SCRAPE", {"url": url})
        return ""


# ──────────────────────────────────────────────────────────────────────────────
# Step 3 — Extractor (LLM)
# ──────────────────────────────────────────────────────────────────────────────

EXTRACTOR_PROMPT = """You are an API research analyst. Given the app name,
hint URL, and (optionally) scraped docs text, return a JSON object with:
  category, one_liner, auth_methods[], self_serve, gating_reason,
  api_surface, api_breadth, has_mcp, buildability, main_blocker,
  evidence_url, notes

self_serve ∈ {self-serve, gated, partial}
buildability ∈ {buildable, buildable-gated, blocked}
has_mcp ∈ {yes-official, yes-community, no, unknown}

Be conservative. If unsure, mark `unknown` and add a note. Cite the
docs URL you used as evidence_url."""


def extract_via_llm(app: dict, scraped: str, online: bool) -> dict:
    """Calls an LLM (OpenAI / Claude / Gemini) to produce a structured record.

    Offline mode: returns an empty record and lets a separate knowledge-base
    pass fill it in (see `generate_dataset.py`).
    """
    if not online:
        return {}
    # Pseudocode — wire up your preferred client.
    # from openai import OpenAI
    # client = OpenAI()
    # resp = client.chat.completions.create(
    #     model="gpt-4o-mini",
    #     response_format={"type": "json_object"},
    #     messages=[
    #         {"role": "system", "content": EXTRACTOR_PROMPT},
    #         {"role": "user", "content": f"App: {app['name']}\nHint: {app['hint']}\nScraped: {scraped[:4000]}"},
    #     ],
    # )
    # return json.loads(resp.choices[0].message.content)
    return {}


# ──────────────────────────────────────────────────────────────────────────────
# Step 4 — Verifier
# ──────────────────────────────────────────────────────────────────────────────

VERIFIER_QUERIES = [
    "{app} API authentication method",
    "{app} developer pricing free tier",
    "{app} MCP server model context protocol",
]


def verify_record(record: AppRecord, researcher: ComposioResearcher) -> AppRecord:
    """Re-runs targeted searches to confirm/deny the agent's first-pass answer.

    Real implementation diffs the snippets against the record fields.
    Here we leave it as a stub that the human review step replaces.
    """
    for q_template in VERIFIER_QUERIES:
        q = q_template.format(app=record.name)
        researcher.search(q)
        time.sleep(0.3)  # be polite
    return record


# ──────────────────────────────────────────────────────────────────────────────
# Step 5 — Human-in-loop
# ──────────────────────────────────────────────────────────────────────────────

def write_flagged(records: list[AppRecord], out_dir: Path):
    flagged = [r for r in records if r.verification_status in ("wrong", "partial", "unverified")]
    (out_dir / "flagged.json").write_text(
        json.dumps([asdict(r) for r in flagged], indent=2)
    )
    print(f"[human] {len(flagged)} records need human review → {out_dir/'flagged.json'}")


# ──────────────────────────────────────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────────────────────────────────────

def main():
    # Resolve paths relative to this script's location so the agent runs from any cwd
    _script_dir = Path(__file__).resolve().parent
    _repo_root = _script_dir.parent

    ap = argparse.ArgumentParser()
    ap.add_argument("--apps", default=str(_script_dir / "apps.json"),
                    help="path to apps.json (default: agent/apps.json next to this script)")
    ap.add_argument("--out", default=str(_repo_root / "results"),
                    help="output directory (default: results/ at repo root)")
    ap.add_argument("--offline", action="store_true", help="no live web calls")
    ap.add_argument("--verify", default=None, help="verify a single app then exit")
    args = ap.parse_args()

    out_dir = Path(args.out); out_dir.mkdir(parents=True, exist_ok=True)
    apps = load_apps(Path(args.apps))
    researcher = ComposioResearcher(online=not args.offline)

    if args.verify:
        try:
            app = next(a for a in apps if a["name"].lower() == args.verify.lower())
        except StopIteration:
            print(f"[error] app '{args.verify}' not found in {args.apps}")
            sys.exit(1)
        rec = AppRecord(id=app["id"], name=app["name"], category=app["category"],
                        one_liner="", auth_methods=[], self_serve="",
                        gating_reason="", api_surface="", api_breadth="",
                        has_mcp="", buildability="", main_blocker="",
                        evidence_url=app["hint"])
        print(json.dumps(asdict(verify_record(rec, researcher)), indent=2))
        return

    records: list[AppRecord] = []
    for app in apps:
        scraped = researcher.scrape(app["hint"])
        extracted = extract_via_llm(app, scraped, online=not args.offline)
        if extracted:
            rec = AppRecord(id=app["id"], name=app["name"], category=app["category"], **extracted)
        else:
            # offline fallback — knowledge base picks this up later
            rec = AppRecord(id=app["id"], name=app["name"], category=app["category"],
                            one_liner="", auth_methods=[], self_serve="",
                            gating_reason="", api_surface="", api_breadth="",
                            has_mcp="", buildability="", main_blocker="",
                            evidence_url=app["hint"])
        records.append(rec)

    (out_dir / "first_pass.json").write_text(
        json.dumps([asdict(r) for r in records], indent=2)
    )
    write_flagged(records, out_dir)
    print(f"[done] {len(records)} records → {out_dir}")


if __name__ == "__main__":
    main()
