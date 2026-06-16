# ⭐ The Scientist

> *Look at the stars... look how they shine for you.*

A fully automated monthly newsletter that discovers and curates the brightest ML/AI papers for practitioners. Posted to Slack. Zero human input required after setup.

## How It Works

Every month, the pipeline runs these 5 steps:

### Step 1 — Cast a wide net (3 sources, last 35 days)

Papers are pulled from three independent sources simultaneously:

| Source | What It Catches | Coverage |
|--------|-----------------|----------|
| **arXiv + Semantic Scholar keyword search** | Papers matching topics you explicitly configured (e.g. "large language model inference optimization") | Configured in `sources.yaml` — edit to add/remove topics |
| **Hugging Face Daily Papers** | Papers the ML community is actively upvoting right now — catches novelty that no keyword search would find | Fully dynamic — driven live by the HF community |
| **Semantic Scholar Recommendations** | Papers conceptually similar to past curated issues — seeded by the rolling 120-paper history | Grows with every issue as new papers are added to the seed pool |

> **Important limitation:** The keyword searches and topic categories are **frozen at setup time**. If a new paradigm emerges (e.g. "test-time compute scaling"), the pipeline will miss it via keyword search until you manually add it to `sources.yaml`. The only automatic safety nets are HF Daily Papers (catches community buzz on anything) and the seed recommendations (which gradually drift toward new areas as curated papers accumulate).

### Step 2 — Score and shortlist (no AI — pure formula)

Each paper gets a numeric score. Papers with no abstract, no keyword match, no known institution, no tracked author, and fewer than 5 HF upvotes are dropped. The rest are scored:

| Signal | Weight | Why |
|--------|--------|-----|
| Citation velocity (citations ÷ age in months) | High | Fast-spreading papers are being noticed |
| Influential citations | Medium | Counts only citations that themselves get cited |
| Venue prestige (NeurIPS, ICML, etc.) | Medium | Peer-reviewed venues get a boost |
| Known institution (Google, Meta, Anthropic, Stanford…) | Bonus +15 | Track record of impactful work |
| Key author match | Bonus +10 | Researchers you've explicitly flagged |
| Keyword category match | Bonus up to +12 | Relevance to your configured topics |
| HF upvote count | Bonus up to +20 | Community excitement signal |

The top 60 papers by score move to Step 3.

### Step 3 — Claude picks the final 10

Claude receives the 60 shortlisted papers (title, abstract, authors, citation stats, HF upvotes, institution) and is asked to select the 10 that practitioners **must** know about — ranked by practitioner impact, not academic novelty. Claude writes a 2–3 sentence summary and a "Why it matters" line for each.

Papers are rejected if they are: pure theory with no path to practice, incremental niche benchmarks, from unknown groups with no traction, or too domain-specific.

### Step 4 — Post to Slack

The formatted newsletter is posted to your configured Slack channel with links, authors, venue, and summaries.

### Step 5 — Update the seed pool (self-improving)

The 10 selected papers are added to the Layer 3 seed list in `sources.yaml` and committed back to the repo. The pool is capped at 120 papers (oldest drop off). This means the recommendations engine gradually learns your editorial taste over time — without you touching anything.

---

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
5. Commits updated `sources.yaml` (new seeds) back to the repo
6. Archives `latest_issue.json` as a workflow artifact

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
- `seed_papers` — Layer 3 seed pool (auto-updated each run; rolling 120-paper window)
- `venue_prestige` — how venues are scored
- `newsletter.size` — papers per issue (default: 10)

## Cost Per Run

- **Claude API**: ~$0.15-0.25 per month (one Sonnet call)
- Everything else: free (arXiv, Semantic Scholar, HF, GitHub Actions)

## Files

| File | Purpose |
|------|---------|
| `pipeline.py` | Core 3-layer pipeline + pre-filtering + Claude API call |
| `sources.yaml` | All editorial decisions (institutions, authors, keywords, venues) |
| `requirements.txt` | Just `pyyaml` |
| `latest_issue.json` | Most recent newsletter (gitignored locally; archived as GitHub Actions artifact) |
| `.github/workflows/newsletter.yml` | Cron job + secrets injection |
| `SOURCE_CURATION_ANALYSIS.md` | How the sources were chosen |

---

Made with love by [@bforbesc](https://github.com/bforbesc) and Claudia ❤️
