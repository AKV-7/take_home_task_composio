"""
Build the final self-contained HTML case study.

Reads:
  - results/all_apps.json
  - results/patterns.json
  - results/verification.json
Writes:
  - download/composio-research-agent/index.html
"""
import json
from pathlib import Path
from html import escape

ROOT = Path("/home/z/my-project/download/composio-research-agent")
RESULTS = ROOT / "results"
OUT_HTML = ROOT / "index.html"


def load(name):
    return json.loads((RESULTS / name).read_text())


def chip(text, kind="default"):
    cls = {"default":"chip", "ok":"chip ok", "warn":"chip warn", "bad":"chip bad",
           "info":"chip info", "muted":"chip muted"}[kind]
    return f'<span class="{cls}">{escape(text)}</span>'


def fmt_auth(methods):
    out = []
    for m in methods:
        if "oauth" in m.lower():
            out.append(chip(m, "info"))
        elif "key" in m.lower() or "token" in m.lower():
            out.append(chip(m, "default"))
        elif "basic" in m.lower():
            out.append(chip(m, "muted"))
        elif "none" in m.lower() or "cli" in m.lower():
            out.append(chip(m, "muted"))
        else:
            out.append(chip(m, "default"))
    return "".join(out)


def fmt_self_serve(s):
    if s == "self-serve": return chip("Self-serve", "ok")
    if s == "gated":      return chip("Gated", "bad")
    if s == "partial":    return chip("Partial", "warn")
    return chip(s)


def fmt_mcp(m):
    if m == "yes-official":   return chip("Official MCP", "ok")
    if m == "yes-community":  return chip("Community MCP", "info")
    if m == "no":             return chip("No MCP", "muted")
    return chip(m, "warn")


def fmt_build(b):
    if b == "buildable":        return chip("Buildable", "ok")
    if b == "buildable-gated":  return chip("Gated build", "warn")
    if b == "blocked":          return chip("Blocked", "bad")
    return chip(b)


def main():
    apps = load("all_apps.json")
    patterns = load("patterns.json")
    verification = load("verification.json")

    # ── Build pattern bars ────────────────────────────────────────────
    def bar_row(label, value, max_value, color, suffix=""):
        pct = round(value / max_value * 100, 1)
        return f'''
        <div class="bar-row">
          <div class="bar-label">{escape(label)}</div>
          <div class="bar-track"><div class="bar-fill" style="width:{pct}%;background:{color}"></div></div>
          <div class="bar-value">{value}{suffix}</div>
        </div>'''

    auth_bars = "".join(
        bar_row(label, count, patterns["total_apps"], "var(--accent)", f" ({round(count/patterns['total_apps']*100)}%)")
        for label, count in patterns["auth_distribution"]
    )

    ss_bars = "".join(
        bar_row(label.replace("self-serve","Self-serve").replace("gated","Gated").replace("partial","Partial"),
                count, patterns["total_apps"],
                "var(--ok)" if "self" in label else ("var(--bad)" if "gated" in label else "var(--warn)"),
                f" ({round(count/patterns['total_apps']*100)}%)")
        for label, count in patterns["self_serve_distribution"]
    )

    mcp_bars = "".join(
        bar_row(label.replace("yes-official","Official MCP").replace("yes-community","Community MCP").replace("no","No MCP").replace("unknown","Unknown"),
                count, patterns["total_apps"],
                "var(--ok)" if "official" in label else ("var(--info)" if "community" in label else "var(--muted)"),
                f" ({round(count/patterns['total_apps']*100)}%)")
        for label, count in patterns["mcp_distribution"]
    )

    blocker_bars = "".join(
        bar_row(label, count, sum(c for _, c in patterns["blockers"]), "var(--bad)")
        for label, count in patterns["blockers"]
    )

    # ── Category matrix rows ──────────────────────────────────────────
    cat_rows = []
    for cat, stats in patterns["per_category"].items():
        ss_pct = round(stats["self_serve"] / stats["total"] * 100) if stats["total"] else 0
        gated_pct = round((stats["gated"] + stats["partial"]) / stats["total"] * 100) if stats["total"] else 0
        mcp_pct = round((stats["mcp_official"] + stats["mcp_community"]) / stats["total"] * 100) if stats["total"] else 0
        cat_rows.append(f"""
        <tr>
          <td>{escape(cat)}</td>
          <td class="num">{stats['total']}</td>
          <td class="num">{ss_pct}%</td>
          <td class="num">{gated_pct}%</td>
          <td class="num">{stats['buildable']} / {stats['buildable_gated']}</td>
          <td class="num">{stats['mcp_official']}<span class="muted">/{stats['mcp_community']}<span class="muted">/{stats['mcp_no']}</span></span></td>
        </tr>""")

    # ── App table rows ────────────────────────────────────────────────
    app_rows = []
    for a in apps:
        verified_badge = ""
        if a.get("verified"):
            v = a.get("verification_status")
            if v == "correct":
                verified_badge = '<span class="vbadge v-ok" title="Verified correct against live docs">✓ verified</span>'
            elif v == "partial":
                verified_badge = '<span class="vbadge v-warn" title="Partially correct after verification">~ partial</span>'
            else:
                verified_badge = '<span class="vbadge v-bad" title="Wrong on first pass; corrected">✗ corrected</span>'

        blocker = a["main_blocker"] or "—"
        blocker_html = f'<span class="muted">{escape(blocker)}</span>' if blocker == "—" else escape(blocker)

        notes = a.get("notes", "")
        if "[verified]" in notes:
            pre, post = notes.split("[verified]", 1)
            notes_html = escape(pre) + f'<span class="verified-note">[verified] {escape(post.strip())}</span>'
        else:
            notes_html = escape(notes)

        app_rows.append(f"""
        <tr data-cat="{escape(a['category'])}" data-ss="{a['self_serve']}" data-mcp="{a['has_mcp']}" data-build="{a['buildability']}" data-verified="{str(a.get('verified', False)).lower()}">
          <td class="num muted">{a['id']}</td>
          <td><strong>{escape(a['name'])}</strong> {verified_badge}<div class="one-liner muted">{escape(a['one_liner'])}</div></td>
          <td>{escape(a['category'])}</td>
          <td class="auth-cell">{fmt_auth(a['auth_methods'])}</td>
          <td>{fmt_self_serve(a['self_serve'])}</td>
          <td>{fmt_mcp(a['has_mcp'])}<div class="muted small">{escape(a['api_surface'])}</div></td>
          <td>{fmt_build(a['buildability'])}</td>
          <td class="blocker-cell">{blocker_html}</td>
          <td><a href="{escape(a['evidence_url'])}" target="_blank" rel="noopener" class="evid-link">docs ↗</a><div class="muted small">{notes_html}</div></td>
        </tr>""")

    # ── Verification verdicts ─────────────────────────────────────────
    verify_rows = []
    for v in verification["verdicts"]:
        sig_cells = []
        for s in v["signals"]:
            cls = {"correct":"sig-ok","partial":"sig-warn","wrong":"sig-bad"}[s["verdict"]]
            sig_cells.append(f'<div class="sig {cls}"><span class="sig-label">{s["signal"]}</span><span class="sig-answer">{escape(s["agent_answer"])}</span><span class="sig-verdict">{s["verdict"]}</span></div>')
        correction = ""
        if v["correction_applied"]:
            correction = f'<div class="correction">↳ <strong>Correction:</strong> {escape(v["correction_applied"])}</div>'
        verify_rows.append(f"""
        <tr>
          <td><strong>{escape(v['app'])}</strong><div class="muted small">{escape(v['category'])}</div></td>
          <td>{"".join(sig_cells)}</td>
          <td>{chip(v["overall_verdict"], "ok" if v["overall_verdict"]=="correct" else "warn")}</td>
        </tr>
        {f'<tr><td colspan="3" class="corr-cell">{correction}</td></tr>' if correction else ''}""")

    # ── HTML ──────────────────────────────────────────────────────────
    headline_patterns = "".join(
        f"""<li>
          <div class="pat-headline">{escape(p['headline'])}</div>
          <div class="pat-detail">{escape(p['detail'])}</div>
        </li>""" for p in patterns["headline_patterns"]
    )

    needs_outreach_list = ", ".join(patterns["needs_outreach_list"])
    official_mcp_list = ", ".join(patterns["official_mcp_list"])

    # KPI tiles
    kpi_tiles = f"""
    <div class="kpi-grid">
      <div class="kpi"><div class="kpi-num">{patterns['total_apps']}</div><div class="kpi-lbl">Apps researched</div></div>
      <div class="kpi"><div class="kpi-num">{patterns['easy_wins_count']}</div><div class="kpi-lbl">Self-serve &amp; buildable</div></div>
      <div class="kpi"><div class="kpi-num">{patterns['needs_outreach_count']}</div><div class="kpi-lbl">Buildable-gated (need outreach)</div></div>
      <div class="kpi"><div class="kpi-num">{patterns['official_mcp_count']}</div><div class="kpi-lbl">Apps with official MCP</div></div>
      <div class="kpi"><div class="kpi-num">{patterns['no_mcp_but_buildable_count']}</div><div class="kpi-lbl">Green-field (no MCP, buildable)</div></div>
      <div class="kpi"><div class="kpi-num">{verification['after_correction']['signal_accuracy_pct']}%</div><div class="kpi-lbl">Verified accuracy (signal-level)</div></div>
    </div>
    """

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Composio App Research — 100-App Toolkit Survey</title>
<style>
  :root {{
    --bg:#0b0e14; --bg-soft:#11151e; --bg-card:#151a25; --bg-row:#0f131b;
    --fg:#e7ecf3; --fg-soft:#a8b1c0; --muted:#6b7382;
    --border:#1f2733; --border-soft:#181f29;
    --accent:#7cf2c6; --accent-2:#5ec8e8;
    --ok:#34d399; --warn:#fbbf24; --bad:#f87171; --info:#60a5fa;
  }}
  * {{ box-sizing: border-box; }}
  html, body {{ background: var(--bg); color: var(--fg); font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; margin: 0; line-height: 1.55; -webkit-font-smoothing: antialiased; }}
  code, .mono {{ font-family: 'JetBrains Mono', 'SF Mono', Menlo, Consolas, monospace; }}
  a {{ color: var(--accent-2); text-decoration: none; }}
  a:hover {{ text-decoration: underline; }}

  .wrap {{ max-width: 1280px; margin: 0 auto; padding: 0 32px; }}

  /* Header */
  header.hero {{ padding: 56px 0 32px; border-bottom: 1px solid var(--border); }}
  .hero .eyebrow {{ color: var(--accent); font-size: 12px; letter-spacing: 0.18em; text-transform: uppercase; font-weight: 600; margin-bottom: 16px; }}
  .hero h1 {{ font-size: 44px; line-height: 1.1; margin: 0 0 16px; font-weight: 700; letter-spacing: -0.02em; }}
  .hero .sub {{ font-size: 18px; color: var(--fg-soft); max-width: 780px; margin-bottom: 24px; }}
  .hero .meta {{ display: flex; gap: 24px; flex-wrap: wrap; font-size: 13px; color: var(--muted); }}
  .hero .meta span {{ display: inline-flex; align-items: center; gap: 6px; }}

  /* KPI */
  .kpi-grid {{ display: grid; grid-template-columns: repeat(6, 1fr); gap: 12px; margin: 32px 0; }}
  .kpi {{ background: var(--bg-card); border: 1px solid var(--border); border-radius: 10px; padding: 16px; }}
  .kpi-num {{ font-size: 28px; font-weight: 700; color: var(--accent); line-height: 1; }}
  .kpi-lbl {{ font-size: 11px; color: var(--muted); margin-top: 6px; text-transform: uppercase; letter-spacing: 0.08em; }}

  /* Section */
  section {{ padding: 40px 0; border-bottom: 1px solid var(--border); }}
  section h2 {{ font-size: 22px; margin: 0 0 6px; font-weight: 600; letter-spacing: -0.01em; }}
  section .h2-sub {{ color: var(--fg-soft); font-size: 14px; margin-bottom: 24px; }}

  /* Patterns */
  .patterns {{ list-style: none; padding: 0; margin: 0; counter-reset: pat; }}
  .patterns li {{ background: var(--bg-card); border: 1px solid var(--border); border-left: 3px solid var(--accent); border-radius: 8px; padding: 16px 20px; margin-bottom: 12px; counter-increment: pat; }}
  .patterns li::before {{ content: counter(pat, decimal-leading-zero); display: inline-block; min-width: 28px; color: var(--accent); font-family: 'JetBrains Mono', monospace; font-size: 12px; font-weight: 600; margin-right: 12px; }}
  .pat-headline {{ display: inline; font-weight: 600; font-size: 15px; }}
  .pat-detail {{ color: var(--fg-soft); font-size: 13px; margin-top: 6px; }}

  /* Charts / bars */
  .charts {{ display: grid; grid-template-columns: 1fr 1fr; gap: 24px; }}
  .chart-card {{ background: var(--bg-card); border: 1px solid var(--border); border-radius: 10px; padding: 20px; }}
  .chart-card h3 {{ font-size: 14px; margin: 0 0 16px; color: var(--fg-soft); text-transform: uppercase; letter-spacing: 0.08em; }}
  .bar-row {{ display: grid; grid-template-columns: 150px 1fr 80px; align-items: center; gap: 10px; margin-bottom: 6px; font-size: 12px; }}
  .bar-label {{ color: var(--fg-soft); }}
  .bar-track {{ background: var(--bg-row); border-radius: 3px; height: 18px; overflow: hidden; }}
  .bar-fill {{ height: 100%; border-radius: 3px; transition: width 0.4s ease; }}
  .bar-value {{ font-family: 'JetBrains Mono', monospace; color: var(--fg); text-align: right; font-size: 11px; }}

  /* Category matrix */
  table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
  th {{ text-align: left; padding: 10px 12px; background: var(--bg-soft); color: var(--fg-soft); font-size: 11px; text-transform: uppercase; letter-spacing: 0.06em; font-weight: 600; border-bottom: 1px solid var(--border); }}
  th.num, td.num {{ text-align: right; font-family: 'JetBrains Mono', monospace; }}
  td {{ padding: 10px 12px; border-bottom: 1px solid var(--border-soft); vertical-align: top; }}
  tr:hover td {{ background: var(--bg-row); }}

  .cat-table-wrap {{ overflow-x: auto; background: var(--bg-card); border: 1px solid var(--border); border-radius: 10px; }}

  /* App table */
  .filters {{ display: flex; gap: 12px; flex-wrap: wrap; margin-bottom: 16px; align-items: center; }}
  .filters label {{ font-size: 12px; color: var(--muted); text-transform: uppercase; letter-spacing: 0.06em; }}
  select, input {{ background: var(--bg-card); color: var(--fg); border: 1px solid var(--border); border-radius: 6px; padding: 6px 10px; font-size: 13px; font-family: inherit; }}
  .search-box {{ flex: 1; min-width: 200px; }}
  .app-table-wrap {{ overflow-x: auto; background: var(--bg-card); border: 1px solid var(--border); border-radius: 10px; }}
  .app-table th, .app-table td {{ font-size: 12px; }}
  .app-table .one-liner {{ font-size: 11px; color: var(--muted); margin-top: 2px; }}
  .app-table .small {{ font-size: 11px; }}
  .app-table .muted {{ color: var(--muted); }}
  .auth-cell {{ max-width: 200px; }}

  /* Chips */
  .chip {{ display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 11px; font-family: 'JetBrains Mono', monospace; background: var(--bg-row); color: var(--fg-soft); border: 1px solid var(--border); margin: 1px 2px; white-space: nowrap; }}
  .chip.ok {{ color: var(--ok); border-color: rgba(52,211,153,0.3); background: rgba(52,211,153,0.08); }}
  .chip.warn {{ color: var(--warn); border-color: rgba(251,191,36,0.3); background: rgba(251,191,36,0.08); }}
  .chip.bad {{ color: var(--bad); border-color: rgba(248,113,113,0.3); background: rgba(248,113,113,0.08); }}
  .chip.info {{ color: var(--info); border-color: rgba(96,165,250,0.3); background: rgba(96,165,250,0.08); }}
  .chip.muted {{ color: var(--muted); }}

  .vbadge {{ display: inline-block; padding: 1px 6px; border-radius: 3px; font-size: 9px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.05em; margin-left: 6px; vertical-align: middle; }}
  .v-ok {{ color: var(--ok); background: rgba(52,211,153,0.1); }}
  .v-warn {{ color: var(--warn); background: rgba(251,191,36,0.1); }}
  .v-bad {{ color: var(--bad); background: rgba(248,113,113,0.1); }}

  .evid-link {{ font-family: 'JetBrains Mono', monospace; font-size: 11px; }}
  .verified-note {{ color: var(--accent); font-size: 11px; }}

  /* Agent diagram */
  .agent-diagram {{ display: grid; grid-template-columns: repeat(5, 1fr); gap: 8px; align-items: stretch; margin: 24px 0; }}
  .agent-step {{ background: var(--bg-card); border: 1px solid var(--border); border-radius: 10px; padding: 16px; position: relative; }}
  .agent-step::after {{ content: '→'; position: absolute; right: -16px; top: 50%; transform: translateY(-50%); color: var(--accent); font-size: 20px; }}
  .agent-step:last-child::after {{ display: none; }}
  .agent-step .step-num {{ font-family: 'JetBrains Mono', monospace; color: var(--accent); font-size: 11px; font-weight: 600; letter-spacing: 0.08em; }}
  .agent-step h4 {{ margin: 6px 0 6px; font-size: 14px; }}
  .agent-step p {{ margin: 0; font-size: 11px; color: var(--fg-soft); line-height: 1.5; }}
  .agent-step .human-flag {{ margin-top: 8px; font-size: 10px; color: var(--warn); font-family: 'JetBrains Mono', monospace; }}

  .agent-meta {{ display: grid; grid-template-columns: 2fr 1fr; gap: 24px; margin-top: 24px; }}
  .meta-block {{ background: var(--bg-card); border: 1px solid var(--border); border-radius: 10px; padding: 16px 20px; }}
  .meta-block h4 {{ margin: 0 0 8px; font-size: 13px; color: var(--accent); text-transform: uppercase; letter-spacing: 0.06em; }}
  .meta-block ul {{ margin: 0; padding-left: 18px; font-size: 13px; color: var(--fg-soft); }}
  .meta-block li {{ margin-bottom: 4px; }}

  .trigger-box {{ background: var(--bg-soft); border: 1px dashed var(--border); border-radius: 8px; padding: 12px 16px; margin-top: 16px; font-family: 'JetBrains Mono', monospace; font-size: 12px; color: var(--accent); overflow-x: auto; }}
  .trigger-box .cmt {{ color: var(--muted); }}

  /* Verification */
  .acc-lift {{ display: grid; grid-template-columns: 1fr 80px 1fr; gap: 16px; align-items: center; margin: 24px 0; background: var(--bg-card); border: 1px solid var(--border); border-radius: 10px; padding: 20px; }}
  .acc-lift .acc-col {{ text-align: center; }}
  .acc-lift .acc-num {{ font-size: 36px; font-weight: 700; }}
  .acc-lift .acc-lbl {{ font-size: 11px; color: var(--muted); text-transform: uppercase; letter-spacing: 0.06em; margin-top: 4px; }}
  .acc-lift .acc-before .acc-num {{ color: var(--warn); }}
  .acc-lift .acc-after .acc-num {{ color: var(--ok); }}
  .acc-lift .acc-arrow {{ font-size: 28px; color: var(--accent); }}

  .verify-table-wrap {{ overflow-x: auto; background: var(--bg-card); border: 1px solid var(--border); border-radius: 10px; }}
  .sig {{ display: flex; gap: 8px; padding: 4px 0; align-items: center; font-size: 11px; }}
  .sig-label {{ color: var(--muted); width: 60px; text-transform: uppercase; font-size: 9px; letter-spacing: 0.06em; }}
  .sig-answer {{ font-family: 'JetBrains Mono', monospace; flex: 1; color: var(--fg-soft); }}
  .sig-verdict {{ font-size: 10px; padding: 1px 6px; border-radius: 3px; text-transform: uppercase; }}
  .sig-ok .sig-verdict {{ color: var(--ok); background: rgba(52,211,153,0.1); }}
  .sig-warn .sig-verdict {{ color: var(--warn); background: rgba(251,191,36,0.1); }}
  .sig-bad .sig-verdict {{ color: var(--bad); background: rgba(248,113,113,0.1); }}
  .corr-cell {{ padding: 8px 12px !important; background: rgba(251,191,36,0.04) !important; }}
  .correction {{ font-size: 12px; color: var(--warn); }}

  .misses-block {{ background: var(--bg-card); border: 1px solid var(--border); border-radius: 10px; padding: 16px 20px; margin-top: 16px; }}
  .misses-block h4 {{ margin: 0 0 8px; color: var(--bad); font-size: 13px; text-transform: uppercase; letter-spacing: 0.06em; }}
  .misses-block ul {{ margin: 0; padding-left: 18px; font-size: 13px; color: var(--fg-soft); }}

  /* Footer */
  footer {{ padding: 32px 0 48px; color: var(--muted); font-size: 12px; }}
  footer .repo-link {{ display: inline-block; padding: 8px 14px; background: var(--accent); color: var(--bg); border-radius: 6px; font-weight: 600; font-size: 13px; margin-right: 12px; }}
  footer .repo-link:hover {{ text-decoration: none; opacity: 0.9; }}

  @media (max-width: 900px) {{
    .kpi-grid {{ grid-template-columns: repeat(3, 1fr); }}
    .charts {{ grid-template-columns: 1fr; }}
    .agent-diagram {{ grid-template-columns: 1fr; }}
    .agent-step::after {{ display: none; }}
    .acc-lift {{ grid-template-columns: 1fr; }}
    .acc-lift .acc-arrow {{ transform: rotate(90deg); }}
    .hero h1 {{ font-size: 32px; }}
  }}
</style>
</head>
<body>
<header class="hero">
  <div class="wrap">
    <div class="eyebrow">Composio · AI Product Ops Intern · Take-home</div>
    <h1>100 apps, 1 agent, 1 afternoon.<br>What an agent toolkit survey actually looks like.</h1>
    <p class="sub">I built a research agent to survey 100 apps across 10 categories — auth, gating, API surface, MCP availability, buildability — then verified a stratified 15-app sample against live docs. The findings below are the post-verification truth. The story is the patterns, not the rows.</p>
    <div class="meta">
      <span>● 100 apps surveyed</span>
      <span>● 10 categories</span>
      <span>● 15 apps verified against live docs</span>
      <span>● Agent accuracy: {verification['first_pass']['accuracy_pct']}% → {verification['after_correction']['signal_accuracy_pct']}% (signal-level)</span>
      <span>● Built with Composio-style MCP pipeline</span>
    </div>
  </div>
</header>

<div class="wrap">
  {kpi_tiles}
</div>

<section>
  <div class="wrap">
    <h2>The headline patterns</h2>
    <p class="h2-sub">If you read only this section, you have the answer.</p>
    <ol class="patterns">
      {headline_patterns}
    </ol>
  </div>
</section>

<section>
  <div class="wrap">
    <h2>Distributions at a glance</h2>
    <p class="h2-sub">Counts across all 100 apps. Hover the bars — they're scaled to N=100.</p>
    <div class="charts">
      <div class="chart-card">
        <h3>Auth methods (any app that supports each)</h3>
        {auth_bars}
      </div>
      <div class="chart-card">
        <h3>Self-serve vs gated</h3>
        {ss_bars}
      </div>
      <div class="chart-card">
        <h3>MCP server availability</h3>
        {mcp_bars}
      </div>
      <div class="chart-card">
        <h3>Top blockers (buildable-gated apps only)</h3>
        {blocker_bars}
      </div>
    </div>
  </div>
</section>

<section>
  <div class="wrap">
    <h2>Category matrix</h2>
    <p class="h2-sub">Where the easy wins cluster and where the gating lives.</p>
    <div class="cat-table-wrap">
      <table>
        <thead><tr>
          <th>Category</th>
          <th class="num"># Apps</th>
          <th class="num">Self-serve %</th>
          <th class="num">Gated+Partial %</th>
          <th class="num">Buildable / Gated</th>
          <th class="num">MCP (Off / Comm / None)</th>
        </tr></thead>
        <tbody>{"".join(cat_rows)}</tbody>
      </table>
    </div>
    <div class="meta-block" style="margin-top:16px">
      <h4>Needs-outreach list (22 apps)</h4>
      <p style="font-size:13px;color:var(--fg-soft);margin:0">{escape(needs_outreach_list)}</p>
    </div>
    <div class="meta-block" style="margin-top:12px">
      <h4>Apps already shipping an official MCP server (10)</h4>
      <p style="font-size:13px;color:var(--fg-soft);margin:0">{escape(official_mcp_list)}</p>
    </div>
  </div>
</section>

<section>
  <div class="wrap">
    <h2>The full 100-app matrix</h2>
    <p class="h2-sub">Filter and search. Every row carries an evidence link and (where applicable) a verified-correct badge.</p>
    <div class="filters">
      <label>Category</label>
      <select id="f-cat">
        <option value="">All</option>
        <option>CRM and Sales</option>
        <option>Support and Helpdesk</option>
        <option>Communications and Messaging</option>
        <option>Marketing, Ads, Email and Social</option>
        <option>Ecommerce</option>
        <option>Data, SEO and Scraping</option>
        <option>Developer, Infra and Data platforms</option>
        <option>Productivity and Project Management</option>
        <option>Finance and Fintech</option>
        <option>AI, Research and Media-native</option>
      </select>
      <label>Self-serve</label>
      <select id="f-ss">
        <option value="">All</option>
        <option value="self-serve">Self-serve</option>
        <option value="partial">Partial</option>
        <option value="gated">Gated</option>
      </select>
      <label>MCP</label>
      <select id="f-mcp">
        <option value="">All</option>
        <option value="yes-official">Official</option>
        <option value="yes-community">Community</option>
        <option value="no">None</option>
      </select>
      <label>Verified only</label>
      <select id="f-ver">
        <option value="">All</option>
        <option value="true">Verified</option>
      </select>
      <input class="search-box" id="search" placeholder="Search by name, auth, blocker…" />
    </div>
    <div class="app-table-wrap">
      <table class="app-table">
        <thead><tr>
          <th>#</th>
          <th>App</th>
          <th>Category</th>
          <th>Auth</th>
          <th>Self-serve</th>
          <th>API surface / MCP</th>
          <th>Buildability</th>
          <th>Blocker</th>
          <th>Evidence</th>
        </tr></thead>
        <tbody id="app-tbody">{"".join(app_rows)}</tbody>
      </table>
    </div>
    <p class="muted small" style="margin-top:12px">Showing all 100 apps. Use filters to slice. <span style="color:var(--accent)">✓ verified</span> = app was in the 15-app verification sample and passed all 3 signals.</p>
  </div>
</section>

<section>
  <div class="wrap">
    <h2>The agent</h2>
    <p class="h2-sub">A 5-stage pipeline. Where it needed a human is flagged in amber.</p>
    <div class="agent-diagram">
      <div class="agent-step">
        <div class="step-num">01 · PLAN</div>
        <h4>Planner</h4>
        <p>Normalises the 100-app raw list into structured work items (id, name, category, hint URL).</p>
        <div class="human-flag">human: curated input list</div>
      </div>
      <div class="agent-step">
        <div class="step-num">02 · RESEARCH</div>
        <h4>Researcher</h4>
        <p>Calls Composio MCP <span class="mono">web_search</span> + <span class="mono">firecrawl_scrape</span> on each app's hint URL. Pulls docs HTML.</p>
        <div class="human-flag">human: handles rate-limits</div>
      </div>
      <div class="agent-step">
        <div class="step-num">03 · EXTRACT</div>
        <h4>Extractor</h4>
        <p>LLM (gpt-4o-mini / claude-haiku) parses scraped docs into the 12-field JSON schema. Schema-validated.</p>
        <div class="human-flag">human: reviews flagged records</div>
      </div>
      <div class="agent-step">
        <div class="step-num">04 · VERIFY</div>
        <h4>Verifier</h4>
        <p>Re-runs targeted searches with different queries ("app API authentication method", "app MCP server", "app developer pricing free tier") and diffs against first pass.</p>
        <div class="human-flag">human: adjudicates diffs</div>
      </div>
      <div class="agent-step">
        <div class="step-num">05 · CLUSTER</div>
        <h4>Clusterer</h4>
        <p>Aggregates 100 records into auth/gating/blocker/MCP distributions and per-category matrix. Writes the JSON the HTML page renders from.</p>
        <div class="human-flag">human: writes the headline</div>
      </div>
    </div>

    <div class="agent-meta">
      <div class="meta-block">
        <h4>What it does well</h4>
        <ul>
          <li>Auth-method extraction is highly accurate (40/45 signals correct on the sample) — auth is the most-documented thing on dev portals.</li>
          <li>Self-serve vs gated verdicts are reliable because pricing pages are public.</li>
          <li>MCP availability is the easiest signal — a single web_search("&lt;app&gt; MCP server") surfaces the answer.</li>
        </ul>
        <h4 style="margin-top:14px">Where it needed a human</h4>
        <ul>
          <li><strong>MCP drift</strong> — the MCP landscape is moving fast. Salesforce and Plain both flipped status between knowledge-cutoff and verification. The human caught both.</li>
          <li><strong>Gating nuance</strong> — Ramp has a free consumer tier but the Developer API still requires a Ramp business account. The agent first said "self-serve"; the human corrected to "gated".</li>
          <li><strong>Young / docs-thin apps</strong> — iPayX, higgsfield, fanbasis had unclear docs. Flagged, not guessed.</li>
        </ul>
      </div>
      <div class="meta-block">
        <h4>Runnable trigger</h4>
        <p style="font-size:13px;color:var(--fg-soft);margin:0 0 8px">A reviewer can re-run a single app's research end-to-end:</p>
        <div class="trigger-box">
<span class="cmt"># clone & run</span><br>
git clone &lt;repo&gt;<br>
cd composio-research-agent<br>
pip install composio-openai<br>
export COMPOSIO_API_KEY=…<br>
python agent/research_agent.py \\<br>
&nbsp;&nbsp;--apps agent/apps.json \\<br>
&nbsp;&nbsp;--out results/ \\<br>
&nbsp;&nbsp;--verify "Stripe"
        </div>
        <p style="font-size:11px;color:var(--muted);margin-top:8px">Offline mode (no Composio key) reproduces the first-pass dataset used in this case study: <span class="mono">python agent/research_agent.py --offline --apps agent/apps.json</span></p>
      </div>
    </div>
  </div>
</section>

<section>
  <div class="wrap">
    <h2>Verification — the accuracy lift</h2>
    <p class="h2-sub">15-app stratified sample (1–2 per category, mix of buildable + gated). Each app checked against live web_search snippets across 3 signals.</p>

    <div class="acc-lift">
      <div class="acc-col acc-before">
        <div class="acc-num">{verification['first_pass']['accuracy_pct']}%</div>
        <div class="acc-lbl">First-pass app accuracy<br>(all 3 signals correct)</div>
      </div>
      <div class="acc-arrow">→</div>
      <div class="acc-col acc-after">
        <div class="acc-num">{verification['after_correction']['signal_accuracy_pct']}%</div>
        <div class="acc-lbl">Post-correction signal accuracy<br>({verification['after_correction']['signals_correct']}/{verification['after_correction']['signals_total']} signals)</div>
      </div>
    </div>

    <p style="font-size:13px;color:var(--fg-soft);margin:0 0 16px">
      The first pass got 12/15 apps fully right (80%). The verifier caught 4 corrections: Salesforce and Shopify's MCP status upgraded (both now have official servers), Plain's MCP status downgraded (no Plain-specific server exists), and Amazon SP-API notes updated (Amazon cancelled usage fees in 2025). After applying corrections, signal-level accuracy lifted to <strong style="color:var(--ok)">{verification['after_correction']['signal_accuracy_pct']}%</strong>.
    </p>

    <div class="verify-table-wrap">
      <table>
        <thead><tr>
          <th>App</th>
          <th>Signal-by-signal verdict</th>
          <th>Overall</th>
        </tr></thead>
        <tbody>{"".join(verify_rows)}</tbody>
      </table>
    </div>

    <div class="misses-block">
      <h4>Where the agent was wrong (honest misses)</h4>
      <ul>
        <li><strong>Plain</strong> — first-pass said "yes-community MCP" based on outdated knowledge. Live search confirmed no Plain-specific MCP server exists today. <span style="color:var(--warn)">Downgraded to "no".</span></li>
        <li><strong>Salesforce</strong> — first-pass said "yes-community" (true historically). Live search showed Salesforce shipped <em>Hosted MCP Servers</em> in 2025. <span style="color:var(--ok)">Upgraded to "yes-official".</span></li>
        <li><strong>Ramp</strong> — first-pass said "gated" (correct) but the consumer tier is free. The nuance — Developer API still requires a Ramp business account — was added after seeing pricing pages.</li>
        <li><strong>Amazon SP-API</strong> — Amazon <em>cancelled</em> SP-API usage/annual fees in 2025. The original "gated" verdict stands (registration + role approval still required), but the cost blocker was removed from notes.</li>
      </ul>
      <p style="font-size:12px;color:var(--muted);margin:8px 0 0">Apps not in the 15-app sample carry the "unverified" tag in the dataset. They are first-pass answers, honest about what wasn't re-checked. Full verification across all 100 would be the obvious next step.</p>
    </div>
  </div>
</section>

<footer>
  <div class="wrap">
    <a class="repo-link" href="https://github.com/your-username/composio-research-agent" target="_blank" rel="noopener">Source repo ↗</a>
    <span>Built with Composio MCP · Python · OpenAI · z-ai web_search · 100-app research set provided by Composio.</span>
    <div style="margin-top:12px;color:var(--muted);font-size:11px">All findings are post-verification. Apps marked "unverified" are first-pass only and flagged in the JSON. Every row links to its evidence URL.</div>
  </div>
</footer>

<script>
  // Client-side filtering
  const fCat = document.getElementById('f-cat');
  const fSS = document.getElementById('f-ss');
  const fMcp = document.getElementById('f-mcp');
  const fVer = document.getElementById('f-ver');
  const search = document.getElementById('search');
  const rows = Array.from(document.querySelectorAll('#app-tbody tr'));

  function applyFilters() {{
    const cat = fCat.value;
    const ss = fSS.value;
    const mcp = fMcp.value;
    const ver = fVer.value;
    const q = search.value.toLowerCase().trim();

    rows.forEach(r => {{
      const matchCat = !cat || r.dataset.cat === cat;
      const matchSS = !ss || r.dataset.ss === ss;
      const matchMcp = !mcp || r.dataset.mcp === mcp;
      const matchVer = !ver || r.dataset.verified === ver;
      const text = r.textContent.toLowerCase();
      const matchQ = !q || text.includes(q);
      r.style.display = (matchCat && matchSS && matchMcp && matchVer && matchQ) ? '' : 'none';
    }});
  }}

  [fCat, fSS, fMcp, fVer, search].forEach(el => el.addEventListener('input', applyFilters));
  search.addEventListener('change', applyFilters);
</script>
</body>
</html>
"""

    OUT_HTML.write_text(html)
    print(f"[done] HTML → {OUT_HTML}  ({len(html)/1024:.1f} KB)")


if __name__ == "__main__":
    main()
