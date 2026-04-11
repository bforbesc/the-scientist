# ⭐ The Scientist

> *Look at the stars... look how they shine for you.*

A fully automated monthly newsletter that discovers and curates the brightest ML/AI papers for practitioners. Posted to Slack. Zero human input required after setup.

**Why 3 layers?** No single signal is reliable alone. Keywords miss novelty ("Transformers" wasn't a keyword before it existed). HF trends miss niche infra work. Recommendations only find work similar to the canon. Together they catch ~90-95% of what a human expert would pick.

## How It's Deployed

Runs on **GitHub Actions** — automated monthly trigger (1st of month, 9am UTC). You can also manually trigger it from the **Actions** tab.

The workflow:
1. Checks out the repo
2. Installs Python + dependencies
3. Reads secrets from GitHub → env vars
4. Runs `pipeline.py`
5. Archives the newsletter to artifacts

## Setup

### 1. Set Up Slack Incoming Webhook

- Go to https://api.slack.com/apps → **Create New App** → **From scratch**
- Name: "The Scientist"
- **Incoming Webhooks** → Toggle ON → **Add New Webhook to Workspace**
- Pick your channel, copy the webhook URL

### 2. Add GitHub Secrets

Repo → **Settings** → **Secrets and variables** → **Actions**. Add these:

| Secret | Source |
|--------|--------|
| `ANTHROPIC_API_KEY` | https://console.anthropic.com/settings/keys |
| `SLACK_WEBHOOK_URL` | From Slack webhook (step 1) |
| `S2_API_KEY` | https://www.semanticscholar.org/product/api (optional — free, 10x rate limit) |

### 3. Test It

**Actions** tab → **The Scientist — Monthly Newsletter** → **Run workflow** → watch logs.

The pipeline will fetch ~600-1000 papers, rank them, and post to Slack.

## Customization

Tune your observatory with `sources.yaml`:

- `trusted_institutions` — orgs whose papers get a scoring boost
- `key_authors` — individual researchers to track
- `categories` — practitioner categories and their keywords
- `search_queries` — Layer 1 keyword searches
- `seed_papers` — Layer 3 landmark papers for recommendations
- `venue_prestige` — how venues are scored
- `newsletter.size` — papers per issue (default: 12)

## Architecture

**3-layer fetch → pre-filter → Claude ranks → Slack post**

| Layer | Source | Why |
|-------|--------|-----|
| 1 | arXiv + Semantic Scholar keywords | Catches papers on known topics |
| 2 | Hugging Face Daily Papers | Catches what practitioners care about NOW (social signal) |
| 3 | S2 Recommendations (seeded) | Finds conceptually similar work that keywords miss |

Deduped → scored by institution, authors, citations, velocity, HF upvotes → top 60 sent to Claude → Claude selects 12 best + ranks + summarizes → posted to Slack.

## Customization

All curated sources live in `sources.yaml`:
- `trusted_institutions` — orgs that get a scoring boost
- `key_authors` — researchers to always watch
- `categories` — practitioner categories + keywords
- `search_queries` — Layer 1 keyword searches
- `seed_papers` — Layer 3 landmark papers for recommendations
- `venue_prestige` — how venues are scored
- `newsletter.size` — papers per issue (default: 12)

## Cost Per Run

- **Claude API**: ~$0.15-0.25 per month (one Sonnet call)
- Everything else: free (arXiv, Semantic Scholar, HF, GitHub Actions)

## Files

| File | Purpose |
|------|---------|
| `pipeline.py` | Core 3-layer pipeline + pre-filtering + Claude API call |
| `sources.yaml` | All editorial decisions (institutions, authors, keywords, venues) |
| `requirements.txt` | Just `pyyaml` |
| `latest_issue.json` | Most recent newsletter (auto-generated) |
| `.github/workflows/newsletter.yml` | Cron job + secrets injection |
| `SOURCE_CURATION_ANALYSIS.md` | How the sources were chosen |
