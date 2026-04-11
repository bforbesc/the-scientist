# ⭐ The Scientist

> *Look at the stars... look how they shine for you.*

A fully automated monthly newsletter that discovers and curates the brightest ML/AI papers for practitioners. Posted to Slack. Zero human input required after setup.

## How It Works

Every month, the pipeline does this:

1. **Fetch from 3 sources** → ~600-1000 candidate papers from three independent sources (see below)
2. **Pre-filter & score** → Remove low-quality papers, score by institution prestige, author reputation, citation velocity, community upvotes
3. **Send top 60 to Claude** → Claude reads the candidates and selects the 12 most impactful, ranks them, writes 2-3 sentence summaries
4. **Post to Slack** → Formatted newsletter with links and explanations

### The 3 Sources

| Source | What It Catches |
|--------|-----------------|
| **arXiv + Semantic Scholar keyword search** | Papers on topics you explicitly care about (ML, deep learning, agents, etc.) |
| **Hugging Face Daily Papers** | Papers trending in the ML community right now (what practitioners are excited about) |
| **Semantic Scholar Recommendations** | Papers conceptually similar to landmark papers (discovers related work you wouldn't think to search for) |

### Why 3 Sources?

No single source is complete:
- **Keywords alone miss novelty** — "Transformers" wasn't a keyword before Transformers existed. New breakthroughs need novel terminology you can't predict.
- **Community trends alone miss niche work** — Important infrastructure papers don't always trend on Hugging Face. Specialized research stays quiet.
- **Recommendations alone miss unrelated breakthroughs** — You only find papers similar to what you already know about.

**Together they catch ~90-95% of what a human expert curator would pick.**

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

All editorial decisions live in `sources.yaml`:
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
