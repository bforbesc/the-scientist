"""
THE SCIENTIST — Fully Automated Monthly Newsletter Pipeline (v2)

3-Layer Source Strategy:
  Layer 1: arXiv API + Semantic Scholar keyword search (known topics)
  Layer 2: Hugging Face Daily Papers API (social signal / novelty)
  Layer 3: Semantic Scholar Recommendations API (conceptual discovery)

Then:
  Pre-filter by institution, category, key authors
  Send top candidates to Claude API for curation + ranking + summarization
  Post formatted newsletter to Slack

Required env vars:
  ANTHROPIC_API_KEY   — for Claude curation
  SLACK_WEBHOOK_URL   — Slack incoming webhook
  S2_API_KEY          — Semantic Scholar (optional but recommended)
"""

import os
import sys
import json
import time
import logging
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from pathlib import Path

import yaml

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("the-scientist")

# ─── Load Config ──────────────────────────────────────────────────────────────

CONFIG_PATH = Path(__file__).parent / "sources.yaml"
with open(CONFIG_PATH) as f:
    CONFIG = yaml.safe_load(f)

ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"]
SLACK_WEBHOOK_URL = os.environ["SLACK_WEBHOOK_URL"]
S2_API_KEY = os.environ.get("S2_API_KEY", "")

ALL_INSTITUTIONS = []
for tier in CONFIG["trusted_institutions"].values():
    ALL_INSTITUTIONS.extend(tier)

KEY_AUTHORS = set(a.lower() for a in CONFIG.get("key_authors", []))

ALL_KEYWORDS = {}
for cat_id, cat in CONFIG["categories"].items():
    ALL_KEYWORDS[cat_id] = {
        "label": cat["label"],
        "keywords": [k.lower() for k in cat["keywords"]],
    }

NEWSLETTER = CONFIG["newsletter"]

S2_FIELDS = (
    "paperId,title,abstract,year,citationCount,"
    "influentialCitationCount,authors,venue,"
    "publicationDate,externalIds,url,openAccessPdf"
)

# ─── HTTP Helpers ─────────────────────────────────────────────────────────────

def http_get_json(url, headers=None):
    req = urllib.request.Request(url, headers=headers or {})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode())

def http_post_json(url, payload, headers=None):
    data = json.dumps(payload).encode()
    hdrs = {"Content-Type": "application/json"}
    if headers:
        hdrs.update(headers)
    req = urllib.request.Request(url, data=data, headers=hdrs, method="POST")
    with urllib.request.urlopen(req, timeout=120) as resp:
        return json.loads(resp.read().decode())

def slack_post(payload):
    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        SLACK_WEBHOOK_URL, data=data,
        headers={"Content-Type": "application/json"}, method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.status

# ─── LAYER 1: arXiv + Semantic Scholar Keyword Search ─────────────────────────

def fetch_from_semantic_scholar():
    """Keyword search across all configured queries."""
    papers = {}
    headers = {"x-api-key": S2_API_KEY} if S2_API_KEY else {}
    since_year = (datetime.now() - timedelta(days=NEWSLETTER["lookback_days"])).year

    for query in CONFIG["search_queries"]:
        url = (
            f"https://api.semanticscholar.org/graph/v1/paper/search"
            f"?query={urllib.parse.quote(query)}&fields={S2_FIELDS}"
            f"&limit=50&year={since_year}-&fieldsOfStudy=Computer%20Science"
        )
        try:
            data = http_get_json(url, headers)
            for p in data.get("data") or []:
                pid = p.get("paperId")
                if pid and pid not in papers:
                    papers[pid] = p
            log.info(f"  S2 search '{query[:40]}...': {len(data.get('data') or [])} results")
        except Exception as e:
            log.warning(f"  S2 search '{query[:40]}...' failed: {e}")
        time.sleep(0.4 if S2_API_KEY else 1.2)

    log.info(f"Layer 1a — Semantic Scholar keyword search: {len(papers)} unique papers")
    return papers


def fetch_from_arxiv():
    """Fetch recent papers from arXiv across configured categories."""
    papers = {}
    ns = {"atom": "http://www.w3.org/2005/Atom", "arxiv": "http://arxiv.org/schemas/atom"}
    since = datetime.now() - timedelta(days=NEWSLETTER["lookback_days"])

    for cat in CONFIG["arxiv_categories"]:
        query = (
            f"cat:{cat} AND submittedDate:"
            f"[{since.strftime('%Y%m%d')}0000 TO {datetime.now().strftime('%Y%m%d')}2359]"
        )
        url = (
            f"http://export.arxiv.org/api/query"
            f"?search_query={urllib.parse.quote(query)}"
            f"&sortBy=submittedDate&sortOrder=descending&max_results=100"
        )
        try:
            with urllib.request.urlopen(urllib.request.Request(url), timeout=30) as resp:
                root = ET.fromstring(resp.read())
            count = 0
            for entry in root.findall("atom:entry", ns):
                id_el = entry.find("atom:id", ns)
                if id_el is None:
                    continue
                arxiv_id = id_el.text.split("/")[-1].split("v")[0]
                title_el = entry.find("atom:title", ns)
                abstract_el = entry.find("atom:summary", ns)
                pub_el = entry.find("atom:published", ns)
                authors = []
                for a in entry.findall("atom:author", ns):
                    name_el = a.find("atom:name", ns)
                    if name_el is None:
                        continue
                    affs = [af.text for af in a.findall("arxiv:affiliation", ns) if af.text]
                    authors.append({"name": name_el.text, "affiliations": affs})
                papers[arxiv_id] = {
                    "arxiv_id": arxiv_id,
                    "title": title_el.text.strip().replace("\n", " ") if title_el is not None else "",
                    "abstract": abstract_el.text.strip().replace("\n", " ") if abstract_el is not None else "",
                    "authors": authors,
                    "publicationDate": pub_el.text[:10] if pub_el is not None else "",
                    "source": "arxiv",
                }
                count += 1
            log.info(f"  arXiv {cat}: {count} papers")
        except Exception as e:
            log.warning(f"  arXiv {cat} failed: {e}")
        time.sleep(3)  # arXiv rate limit: 3s between requests

    log.info(f"Layer 1b — arXiv: {len(papers)} unique papers")
    return papers

# ─── LAYER 2: Hugging Face Daily Papers ───────────────────────────────────────

def fetch_from_hf_daily_papers():
    """
    Fetch papers from Hugging Face Daily Papers API.
    These are community-curated by AK and upvoted by ML practitioners.
    Best source for catching novelty that keyword search misses.
    """
    papers = {}
    since = datetime.now() - timedelta(days=NEWSLETTER["lookback_days"])

    try:
        # HF Daily Papers API — fetch recent papers
        url = "https://huggingface.co/api/daily_papers?limit=200"
        data = http_get_json(url)

        for item in data:
            # Each item has: paper (with id, title, summary, authors, publishedAt, upvotes)
            paper_data = item.get("paper", item)  # Handle both nested and flat formats
            paper_id = paper_data.get("id", "")
            published = paper_data.get("publishedAt", "")[:10]
            upvotes = item.get("paper", {}).get("upvotes", 0) or item.get("upvotes", 0)

            # Only include papers from our lookback window
            if published:
                try:
                    pub_date = datetime.strptime(published, "%Y-%m-%d")
                    if pub_date < since:
                        continue
                except ValueError:
                    pass

            authors = []
            for a in paper_data.get("authors", []):
                if isinstance(a, dict):
                    authors.append({"name": a.get("name", ""), "affiliations": []})
                elif isinstance(a, str):
                    authors.append({"name": a, "affiliations": []})

            papers[paper_id] = {
                "arxiv_id": paper_id,
                "title": paper_data.get("title", ""),
                "abstract": paper_data.get("summary", ""),
                "authors": authors,
                "publicationDate": published,
                "source": "hf_daily",
                "_hf_upvotes": upvotes,
            }

        log.info(f"Layer 2 — HF Daily Papers: {len(papers)} papers (within lookback window)")
    except Exception as e:
        log.warning(f"Layer 2 — HF Daily Papers failed: {e}")

    return papers

# ─── LAYER 3: Semantic Scholar Recommendations ───────────────────────────────

def fetch_from_s2_recommendations():
    """
    Use S2 Recommendations API seeded with landmark practitioner papers.
    Finds conceptually similar new work we wouldn't know to search for.
    """
    papers = {}
    headers = {"x-api-key": S2_API_KEY} if S2_API_KEY else {}
    seed_ids = CONFIG.get("seed_papers", [])

    if not seed_ids:
        log.warning("Layer 3 — No seed papers configured, skipping recommendations")
        return papers

    # Use list-based recommendations with all seed papers as positive examples
    try:
        payload = {
            "positivePaperIds": seed_ids,
            "negativePaperIds": [],
        }
        url = (
            f"https://api.semanticscholar.org/recommendations/v1/papers/"
            f"?fields={S2_FIELDS}&limit=100"
        )
        data = http_post_json(url, payload, headers)

        since = datetime.now() - timedelta(days=NEWSLETTER["lookback_days"])
        for p in data.get("recommendedPapers", []):
            pub = p.get("publicationDate", "")
            if pub:
                try:
                    if datetime.strptime(pub[:10], "%Y-%m-%d") < since:
                        continue
                except ValueError:
                    pass
            pid = p.get("paperId", "")
            if pid:
                p["source"] = "s2_recs"
                papers[pid] = p

        log.info(f"Layer 3 — S2 Recommendations: {len(papers)} recent papers")
    except Exception as e:
        log.warning(f"Layer 3 — S2 Recommendations failed: {e}")

        # Fallback: single-paper recommendations from a subset of seeds
        log.info("Layer 3 — Falling back to single-paper recommendations")
        for seed_id in seed_ids[:5]:  # Use top 5 seeds to limit API calls
            try:
                url = (
                    f"https://api.semanticscholar.org/recommendations/v1/papers/"
                    f"forpaper/{urllib.parse.quote(seed_id)}"
                    f"?fields={S2_FIELDS}&limit=20"
                )
                data = http_get_json(url, headers)
                since = datetime.now() - timedelta(days=NEWSLETTER["lookback_days"])
                for p in data.get("recommendedPapers", []):
                    pub = p.get("publicationDate", "")
                    if pub:
                        try:
                            if datetime.strptime(pub[:10], "%Y-%m-%d") < since:
                                continue
                        except ValueError:
                            pass
                    pid = p.get("paperId", "")
                    if pid and pid not in papers:
                        p["source"] = "s2_recs"
                        papers[pid] = p
                log.info(f"  S2 recs for {seed_id}: found papers")
            except Exception as e2:
                log.warning(f"  S2 recs for {seed_id} failed: {e2}")
            time.sleep(0.4 if S2_API_KEY else 1.2)

    return papers

# ─── Combine All Layers ──────────────────────────────────────────────────────

def fetch_all_candidates():
    log.info("=" * 60)
    log.info("Step 1: Fetching candidates from all 3 layers")
    log.info("=" * 60)

    # Layer 1
    s2_papers = fetch_from_semantic_scholar()
    arxiv_papers = fetch_from_arxiv()

    # Layer 2
    hf_papers = fetch_from_hf_daily_papers()

    # Layer 3
    rec_papers = fetch_from_s2_recommendations()

    # Merge everything, deduplicating by arXiv ID where possible
    combined = {}
    seen_arxiv_ids = set()

    # S2 papers first (they have citation data)
    for p in s2_papers.values():
        aid = (p.get("externalIds") or {}).get("ArXiv", "")
        key = aid if aid else p["paperId"]
        combined[key] = p
        if aid:
            seen_arxiv_ids.add(aid)

    # arXiv papers (add if not already from S2)
    for aid, p in arxiv_papers.items():
        if aid not in seen_arxiv_ids:
            combined[aid] = p
            seen_arxiv_ids.add(aid)

    # HF Daily Papers (add if not already seen, carry upvotes)
    for aid, p in hf_papers.items():
        if aid in combined:
            # Paper already exists — just add the upvote signal
            combined[aid]["_hf_upvotes"] = p.get("_hf_upvotes", 0)
        elif aid not in seen_arxiv_ids:
            combined[aid] = p
            seen_arxiv_ids.add(aid)

    # S2 Recommendations (add if not already seen)
    for pid, p in rec_papers.items():
        aid = (p.get("externalIds") or {}).get("ArXiv", "")
        key = aid if aid else pid
        if key not in combined and aid not in seen_arxiv_ids:
            combined[key] = p
            if aid:
                seen_arxiv_ids.add(aid)

    log.info(f"Combined unique candidates across all layers: {len(combined)}")
    return list(combined.values())

# ─── Step 2: Pre-filter and Score ─────────────────────────────────────────────

def match_institutions(paper):
    matched = set()
    for a in paper.get("authors") or []:
        blob = (" ".join(a.get("affiliations") or []) + " " + (a.get("name") or "")).lower()
        for inst in ALL_INSTITUTIONS:
            if inst.lower() in blob:
                matched.add(inst)
    return sorted(matched)


def match_key_authors(paper):
    matched = []
    for a in paper.get("authors") or []:
        name = (a.get("name") or "").lower()
        if name in KEY_AUTHORS:
            matched.append(a.get("name", ""))
    return matched


def categorize(paper):
    text = f"{paper.get('title', '')} {paper.get('abstract', '')}".lower()
    cats = []
    for cat_id, cat in ALL_KEYWORDS.items():
        score = sum(1 for k in cat["keywords"] if k in text)
        if score > 0:
            cats.append({"id": cat_id, "label": cat["label"], "score": score})
    return sorted(cats, key=lambda c: -c["score"])


def prefilter_and_score(papers):
    log.info("=" * 60)
    log.info("Step 2: Pre-filtering and scoring")
    log.info("=" * 60)

    now = datetime.now()
    scored = []

    for p in papers:
        abstract = p.get("abstract") or ""
        if len(abstract) < NEWSLETTER["min_abstract_length"]:
            continue

        categories = categorize(p)
        institutions = match_institutions(p)
        key_auth = match_key_authors(p)

        # Allow papers through if they have category match OR institution match
        # OR key author match OR HF upvotes (social signal)
        hf_upvotes = p.get("_hf_upvotes", 0)
        if not categories and not institutions and not key_auth and hf_upvotes < 5:
            continue

        pub = p.get("publicationDate")
        try:
            days = max(1, (now - datetime.strptime(pub[:10], "%Y-%m-%d")).days) if pub else 30
        except (ValueError, TypeError):
            days = 30

        citations = p.get("citationCount") or 0
        influential = p.get("influentialCitationCount") or 0
        venue = p.get("venue") or ""
        venue_score = CONFIG["venue_prestige"].get(venue, CONFIG["venue_prestige"]["default"])

        velocity = (citations / days) * 30
        inst_bonus = 15 if institutions else 0
        author_bonus = 10 if key_auth else 0
        cat_bonus = min(categories[0]["score"] * 3, 12) if categories else 0
        # HF upvotes as social signal — especially valuable for new papers with 0 citations
        hf_bonus = min(hf_upvotes * 0.5, 20)
        # Bonus for papers from recommendations (conceptually relevant)
        rec_bonus = 5 if p.get("source") == "s2_recs" else 0

        pre_score = round(
            velocity * 8
            + influential * 4
            + venue_score * 2
            + inst_bonus
            + author_bonus
            + cat_bonus
            + hf_bonus
            + rec_bonus,
            1,
        )

        p["_meta"] = {
            "institutions": institutions,
            "key_authors": key_auth,
            "categories": [c["label"] for c in categories[:3]],
            "pre_score": pre_score,
            "citations": citations,
            "influential": influential,
            "velocity": round(velocity, 2),
            "hf_upvotes": hf_upvotes,
            "source": p.get("source", "s2"),
        }
        scored.append(p)

    scored.sort(key=lambda p: -p["_meta"]["pre_score"])
    n = NEWSLETTER["candidates_for_claude"]
    log.info(f"After pre-filter: {len(scored)} papers → sending top {n} to Claude")
    return scored[:n]

# ─── Step 3: Claude Curation ─────────────────────────────────────────────────

def curate_with_claude(papers):
    log.info("=" * 60)
    log.info("Step 3: Claude curation")
    log.info("=" * 60)

    candidates = []
    for i, p in enumerate(papers):
        meta = p["_meta"]
        authors = ", ".join(a["name"] for a in (p.get("authors") or [])[:4])
        arxiv_id = (p.get("externalIds") or {}).get("ArXiv", p.get("arxiv_id", ""))
        link = f"https://arxiv.org/abs/{arxiv_id}" if arxiv_id else (p.get("url") or "")

        source_tag = {"hf_daily": "HF-TRENDING", "s2_recs": "RECOMMENDED", "arxiv": "ARXIV", "s2": "S2"}.get(meta["source"], "")
        hf_tag = f" | HF-upvotes: {meta['hf_upvotes']}" if meta["hf_upvotes"] > 0 else ""

        candidates.append(
            f"[{i+1}] {p['title']}\n"
            f"    Authors: {authors}\n"
            f"    Venue: {p.get('venue', 'Preprint')} | Date: {p.get('publicationDate', 'N/A')}\n"
            f"    Citations: {meta['citations']} | Influential: {meta['influential']} | Velocity: {meta['velocity']}/mo{hf_tag}\n"
            f"    Institutions: {', '.join(meta['institutions']) or 'Unknown'}\n"
            f"    Categories: {', '.join(meta['categories']) or 'Uncategorized'}\n"
            f"    Source: {source_tag}\n"
            f"    Link: {link}\n"
            f"    Abstract: {(p.get('abstract') or '')[:400]}...\n"
        )

    month_label = datetime.now().strftime("%B %Y")
    prompt = f"""You are the editor of "The Scientist", a monthly newsletter for ML engineers, data engineers, and data scientists who do consulting work.

Below are {len(papers)} candidate papers from the past month, sourced from:
- Semantic Scholar + arXiv keyword search (known topics)
- Hugging Face Daily Papers (what the ML community is excited about — look for HF-upvotes)
- Semantic Scholar Recommendations (conceptually related to landmark papers — tagged RECOMMENDED)

Your job:
1. SELECT the top {NEWSLETTER['size']} papers that practitioners MUST know about.
2. RANK them by practitioner impact (not academic novelty).
3. SUMMARIZE each in 2-3 sentences focused on what a practitioner needs to know.
4. Add a "WHY IT MATTERS" one-liner for each.

Selection criteria (in order of importance):
- Does this change how practitioners BUILD things? (new tools, techniques, architectures)
- Does this change how practitioners EVALUATE things? (new benchmarks, failure modes)
- Does this come from a team with a track record? (OpenAI, Google, Meta, Anthropic, Stanford, etc.)
- Is this being widely discussed? (high HF upvotes, high citation velocity)
- Would a consultant need to know this to stay credible with clients?

REJECT papers that are: pure theory with no path to practice, incremental niche benchmarks, unknown groups with no traction, too domain-specific (medical NLP etc unless the method is broadly applicable).

PAY SPECIAL ATTENTION to papers tagged RECOMMENDED or HF-TRENDING — these may represent important new directions that don't match traditional keywords.

RESPOND in this exact JSON format (no markdown, no backticks, just raw JSON):
{{
  "month": "{month_label}",
  "editorial_note": "<1-2 sentence theme for this month>",
  "papers": [
    {{
      "rank": 1,
      "candidate_number": <number from list>,
      "title": "<paper title>",
      "summary": "<2-3 sentence practitioner summary>",
      "why_it_matters": "<one sentence>",
      "category": "<Infra & MLOps | Modeling & Architecture | Training & Alignment | Evaluation & Safety | RAG & Retrieval | Agents & Tools | Data Engineering>"
    }}
  ]
}}

CANDIDATES:
{"".join(candidates)}"""

    resp = http_post_json(
        "https://api.anthropic.com/v1/messages",
        payload={"model": NEWSLETTER["model"], "max_tokens": 4096, "messages": [{"role": "user", "content": prompt}]},
        headers={"x-api-key": ANTHROPIC_API_KEY, "anthropic-version": "2023-06-01"},
    )
    text = "".join(b.get("text", "") for b in resp.get("content", []))
    text = text.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    curation = json.loads(text)
    log.info(f"Claude selected {len(curation['papers'])} papers")

    # Enrich with links and metadata from original candidates
    for entry in curation["papers"]:
        idx = entry["candidate_number"] - 1
        if 0 <= idx < len(papers):
            p = papers[idx]
            aid = (p.get("externalIds") or {}).get("ArXiv", p.get("arxiv_id", ""))
            entry["link"] = f"https://arxiv.org/abs/{aid}" if aid else (p.get("url") or "")
            entry["authors"] = ", ".join(a["name"] for a in (p.get("authors") or [])[:3])
            entry["venue"] = p.get("venue") or "Preprint"
            entry["institutions"] = p["_meta"]["institutions"]

    return curation

# ─── Step 4: Post to Slack ────────────────────────────────────────────────────

CATEGORY_EMOJI = {
    "Infra & MLOps": "🔧", "Modeling & Architecture": "🧠",
    "Training & Alignment": "🎯", "Evaluation & Safety": "📊",
    "RAG & Retrieval": "🔍", "Agents & Tools": "🤖", "Data Engineering": "📦",
}

def post_to_slack(curation):
    log.info("=" * 60)
    log.info("Step 4: Posting to Slack")
    log.info("=" * 60)

    blocks = [
        {"type": "header", "text": {"type": "plain_text", "text": f"⭐ The Scientist — {curation['month']}", "emoji": True}},
        {"type": "section", "text": {"type": "mrkdwn", "text": (
            f"_{curation.get('editorial_note', '')}_\n\n"
            f"Top {len(curation['papers'])} papers for ML engineers, data engineers & data scientists."
        )}},
        {"type": "divider"},
    ]

    for entry in curation["papers"]:
        emoji = CATEGORY_EMOJI.get(entry.get("category", ""), "📄")
        insts = f" · {', '.join(entry.get('institutions', []))}" if entry.get("institutions") else ""
        blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": (
            f"{emoji} *#{entry['rank']}* — <{entry.get('link', '')}|{entry['title']}>\n"
            f"_{entry.get('authors', '')}_ · {entry.get('venue', '')}{insts}\n\n"
            f"{entry['summary']}\n\n"
            f"*Why it matters:* {entry['why_it_matters']}"
        )}})
        blocks.append({"type": "divider"})

    blocks.append({"type": "context", "elements": [{"type": "mrkdwn", "text": (
        f"🤖 Curated by Claude · Sources: arXiv + Semantic Scholar + HF Daily Papers + S2 Recommendations · "
        f"{datetime.now().strftime('%Y-%m-%d')}"
    )}]})

    # Slack 50-block limit — split if needed
    for i in range(0, len(blocks), 48):
        status = slack_post({"blocks": blocks[i:i + 48]})
        log.info(f"Slack post chunk status: {status}")
        time.sleep(1)

    log.info("Posted to Slack successfully")

# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    log.info("=" * 60)
    log.info("THE SCIENTIST — Monthly Newsletter Pipeline v2")
    log.info("=" * 60)

    # Step 1: Fetch from all 3 layers
    candidates = fetch_all_candidates()
    if not candidates:
        log.error("No candidates fetched from any source. Exiting.")
        sys.exit(1)

    # Step 2: Pre-filter and score
    shortlist = prefilter_and_score(candidates)
    if not shortlist:
        log.error("No papers survived pre-filtering. Exiting.")
        sys.exit(1)

    # Step 3: Claude curation
    curation = curate_with_claude(shortlist)

    # Step 4: Post to Slack
    post_to_slack(curation)

    # Archive the issue
    output_path = Path(__file__).parent / "latest_issue.json"
    with open(output_path, "w") as f:
        json.dump(curation, f, indent=2)
    log.info(f"Archived to {output_path}")

    log.info("=" * 60)
    log.info("THE SCIENTIST — Done!")
    log.info("=" * 60)


if __name__ == "__main__":
    main()
