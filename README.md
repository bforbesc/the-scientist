# 📡 The Scientist

A fully automated monthly newsletter that curates the top ML/AI papers for practitioners. Posted to Slack. Zero human input required after setup.

## How It Works

```
LAYER 1: arXiv API + Semantic Scholar keyword search
         (catches papers on known topics)
                    +
LAYER 2: Hugging Face Daily Papers API
         (catches what ML community is excited about NOW)
                    +
LAYER 3: Semantic Scholar Recommendations API
         (seeded with 20 landmark papers — finds conceptually similar new work)
                    ↓
         ~600-1000 candidates (deduplicated)
                    ↓
         Pre-filter & score
         (institutions, categories, key authors, HF upvotes, citations)
                    ↓
         Top 60 candidates → Claude API
         (selects 12, ranks, writes practitioner summaries)
                    ↓
         Formatted newsletter → Slack webhook
```

### Why 3 Layers?

No single source is reliable alone:
- **Keywords miss novelty** — "Transformers" wasn't a keyword before Transformers existed
- **Social signals miss niche work** — important infra papers don't always trend on HF
- **Recommendations miss unrelated breakthroughs** — only finds work similar to the canon

Together they cover ~90-95% of what a human expert curator would pick.

## Setup (~15 minutes)

### 1. Create a Slack Incoming Webhook

1. Go to https://api.slack.com/apps → **Create New App** → **From scratch**
2. Name it "The Scientist", pick your workspace
3. **Incoming Webhooks** → Toggle ON → **Add New Webhook to Workspace**
4. Pick the channel (e.g., `#the-scientist`) → Copy the webhook URL

### 2. Get API Keys

| Key | Where | Required? |
|-----|-------|-----------|
| Anthropic API Key | https://console.anthropic.com/settings/keys | Yes |
| Semantic Scholar API Key | https://www.semanticscholar.org/product/api#api-key-form | Recommended (free, 10x rate limit) |

### 3. Create GitHub Repo

```bash
git init the-scientist && cd the-scientist
# Copy: pipeline.py, sources.yaml, requirements.txt, .github/workflows/newsletter.yml
git add . && git commit -m "Initial setup"
git remote add origin <your-repo-url>
git push -u origin main
```

### 4. Add Secrets

Repo → **Settings** → **Secrets and variables** → **Actions**:

| Secret | Value |
|--------|-------|
| `ANTHROPIC_API_KEY` | Your Anthropic key |
| `SLACK_WEBHOOK_URL` | Your Slack webhook URL |
| `S2_API_KEY` | Semantic Scholar key (optional) |

### 5. Test

**Actions** tab → **The Scientist** → **Run workflow** → watch logs.

## Customization

All editorial decisions live in `sources.yaml`:

- `trusted_institutions` — orgs whose papers get a scoring boost
- `key_authors` — individual researchers to track
- `categories` — practitioner categories and their keywords
- `search_queries` — Layer 1 keyword searches
- `seed_papers` — Layer 3 landmark papers for recommendations
- `venue_prestige` — how venues are scored
- `newsletter.size` — papers per issue (default: 12)

## Cost Per Run

- Claude API: ~$0.15-0.25 (one Sonnet call)
- Semantic Scholar: free
- arXiv: free
- HF Daily Papers: free
- GitHub Actions: free (~4 min/month)

## Files

```
├── pipeline.py                    # Full 3-layer pipeline
├── sources.yaml                   # Source curation config
├── requirements.txt               # pyyaml
├── latest_issue.json              # Most recent issue (auto-generated)
├── SOURCE_CURATION_ANALYSIS.md    # How the sources were chosen
└── .github/workflows/
    └── newsletter.yml             # Monthly cron (1st of each month, 9am UTC)
```
