#!/usr/bin/env bash
# Run web_search verification on the 15-app stratified sample.
# Produces 45 JSON files in results/verification_raw/
# (15 apps × 3 signals: auth, MCP, gating).

set -euo pipefail

# Resolve repo root (parent of agent/ dir)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"
RAW_DIR="$REPO_ROOT/results/verification_raw"
mkdir -p "$RAW_DIR"

APPS=(
  "Salesforce"
  "DealCloud"
  "Zendesk"
  "Plain"
  "Slack"
  "Mailchimp"
  "Shopify"
  "Amazon Selling Partner"
  "Firecrawl"
  "GitHub"
  "Snowflake"
  "Notion"
  "Stripe"
  "Ramp"
  "Devin"
)

cd "$RAW_DIR"

for app in "${APPS[@]}"; do
  safe=$(echo "$app" | tr ' ' '_')
  z-ai function -n web_search -a "{\"query\": \"$app API authentication OAuth2 docs\", \"num\": 6}" -o "${safe}_auth.json" 2>/dev/null
  z-ai function -n web_search -a "{\"query\": \"$app MCP server model context protocol\", \"num\": 6}" -o "${safe}_mcp.json" 2>/dev/null
  z-ai function -n web_search -a "{\"query\": \"$app developer pricing free tier self serve\", \"num\": 6}" -o "${safe}_gating.json" 2>/dev/null
  echo "[ok] $app"
done

echo ""
echo "Done. Raw snippets in: $RAW_DIR"
echo "Run 'python $REPO_ROOT/agent/verify_sample.py' to compute accuracy."
