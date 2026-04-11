# THE SCIENTIST — Source Curation Analysis

## The Question
"If I run this pipeline monthly, will I consistently catch the frontier
research that's relevant for data engineers, ML engineers, and data scientists?"

## Honest Assessment of Current sources.yaml

### What It Catches Well
- Papers with established keywords (RAG, LoRA, RLHF, DPO, etc.)
- Papers from known institutions with citation traction
- Papers in cs.CL, cs.LG, cs.AI, cs.IR

### What It Misses (Gaps That Would Make You Look Uninformed)

1. **Papers that CREATE new categories**
   The Transformers paper didn't have "transformer" as a keyword before
   it existed. Flash Attention wasn't filed under "infrastructure."
   → Keyword search is inherently backward-looking.
   → FIX: Add Hugging Face Daily Papers API (community-curated, catches
     novelty) + Semantic Scholar Recommendations API (finds papers
     similar to known landmarks)

2. **Systems/Infra papers from non-ML venues**
   vLLM, PagedAttention, TensorRT-LLM, DeepSpeed — these appear at
   OSDI, SOSP, NSDI, EuroSys, MLSys, not cs.CL/cs.LG.
   → FIX: Add cs.DC (Distributed Computing), cs.PF (Performance),
     and search queries targeting systems venues.

3. **Technical reports and blog posts that never hit arXiv**
   Anthropic's system prompts guide, OpenAI's function calling spec,
   Meta's Llama release post, Google's Gemma technical report.
   → PARTIAL FIX: These often DO hit arXiv as technical reports,
     but with delay. HF Daily Papers catches them faster.
   → REMAINING GAP: Some never hit arXiv. Accept this — the newsletter
     covers papers, not blog posts. Could add a "Notable Releases"
     section later using Claude web search.

4. **Citation velocity is USELESS for papers < 2 weeks old**
   A paper published last week has 0 citations regardless of quality.
   → FIX: Use HF Daily Papers upvotes as the "social signal" for
     recency. Use S2 citations as the "established signal" for
     papers 2-4 weeks old.

5. **arXiv affiliation data is UNRELIABLE**
   The arXiv API's affiliation field is author-supplied and often empty.
   Semantic Scholar is better but still misses ~30% of affiliations.
   → FIX: Also match author NAMES against known researchers from
     trusted institutions. Maintain a seed list of ~50-100 key authors.

6. **The search queries are too specific**
   "LLM agents tool use function calling" won't catch a paper titled
   "Computer Use as an Autonomous Agent" or "SWE-bench."
   → FIX: Use broader queries + the S2 Recommendations API seeded
     with landmark papers to catch conceptually related work.

---

## Improved Source Strategy (3 Layers)

### Layer 1: BROAD NET (catch everything remotely relevant)
- **arXiv API**: cs.CL, cs.LG, cs.AI, cs.IR, cs.DC, cs.SE
  - 6 categories × 100 papers = up to 600 candidates
  - Sorted by submission date, last 35 days
- **Semantic Scholar keyword search**: 16 queries × 50 results
  - Deduplicated against arXiv results
  - Adds citation data, venue, influence scores

### Layer 2: SOCIAL SIGNAL (what the community cares about NOW)
- **Hugging Face Daily Papers API**: https://huggingface.co/api/daily_papers
  - Community-curated by AK + upvoted by ML practitioners
  - Catches novelty that keyword search misses
  - Aggregate last 30 days, rank by upvotes
  - This is the BEST source for "what practitioners are talking about"

### Layer 3: CONCEPTUAL SIMILARITY (find what we don't know to search for)
- **Semantic Scholar Recommendations API**
  - Seed with 20-30 landmark practitioner papers (the "canon")
  - Ask: "what new papers are similar to these?"
  - Catches papers that don't match keywords but ARE related
  - Example: seeding with Flash Attention would surface new
    attention optimization papers even if they use novel terminology

### How These Layers Combine
```
Layer 1 (arXiv + S2 search)     → ~500-800 candidates (broad)
Layer 2 (HF Daily Papers)       → ~100-200 candidates (social signal)
Layer 3 (S2 Recommendations)    → ~100-200 candidates (conceptual)
         ↓ deduplicate
    ~600-1000 unique candidates
         ↓ pre-filter (has abstract, has category match OR institution match)
    ~100-200 candidates
         ↓ send top 60 to Claude API
    Claude selects top 12, ranks, summarizes
         ↓
    Newsletter posted to Slack
```

---

## The Canon: Seed Papers for Recommendations API

These are the landmark practitioner papers. We use them to:
(a) Seed S2 Recommendations API for conceptual discovery
(b) Validate that our pipeline would have caught them if they were new

| Paper | Year | Institution | Venue | arXiv |
|-------|------|-------------|-------|-------|
| Attention Is All You Need | 2017 | Google | NeurIPS | 1706.03762 |
| BERT | 2019 | Google | NAACL | 1810.04805 |
| GPT-2 | 2019 | OpenAI | — | — |
| GPT-3 (Few-Shot Learners) | 2020 | OpenAI | NeurIPS | 2005.14165 |
| RAG | 2020 | Meta/FAIR | NeurIPS | 2005.11401 |
| LoRA | 2021 | Microsoft | ICLR | 2106.09685 |
| InstructGPT / RLHF | 2022 | OpenAI | NeurIPS | 2203.02155 |
| Flash Attention | 2022 | Stanford | NeurIPS | 2205.14135 |
| LLaMA | 2023 | Meta | — | 2302.13971 |
| DPO | 2023 | Stanford | NeurIPS | 2305.18290 |
| Mixtral / MoE | 2024 | Mistral | — | 2401.04088 |
| DeepSeek-V2 | 2024 | DeepSeek | — | 2405.04434 |
| SWE-bench | 2023 | Princeton | ICLR | 2310.06770 |
| Gorilla | 2023 | UC Berkeley | — | 2305.15334 |
| FAISS | 2024 | Meta | — | — |
| vLLM / PagedAttention | 2023 | UC Berkeley | SOSP | 2309.06180 |
| DSPy | 2023 | Stanford | — | 2310.03714 |
| Constitutional AI | 2022 | Anthropic | — | 2212.08073 |
| Gemini | 2024 | Google | — | 2312.11805 |
| Llama 3 | 2024 | Meta | — | 2407.21783 |

---

## Key Authors to Track

These individuals consistently produce practitioner-relevant work.
Used for author-name matching when affiliation data is missing.

### From Tier 1 Institutions
- Ilya Sutskever, Alec Radford, Greg Brockman (OpenAI)
- Dario Amodei, Chris Olah, Tom Brown (Anthropic)
- Jeff Dean, Noam Shazeer, Ashish Vaswani (Google)
- Yann LeCun, Hugo Touvron (Meta)
- Tri Dao (Flash Attention, now Princeton/Together)
- Edward Hu (LoRA, Microsoft → OpenAI)

### From Tier 2
- Percy Liang, Christopher Manning, Matei Zaharia (Stanford)
- Omar Khattab (DSPy, Stanford)
- Lianmin Zheng (vLLM, UC Berkeley)
- Carlos Guestrin (Databricks/Stanford)

---

## Updated arXiv Categories

| Category | Why |
|----------|-----|
| cs.CL | LLMs, NLP, RAG, prompting — core for all 3 roles |
| cs.LG | Training, architectures, optimization — core |
| cs.AI | Agents, reasoning, planning — growing fast |
| cs.IR | Search, embeddings, retrieval — core for data engineers |
| cs.DC | Distributed computing — where infra papers land |
| cs.SE | Software engineering — SWE-bench, code gen, DevOps |

---

## Confidence Level

With all 3 layers active, I estimate:
- **90-95%** of papers that would make it to a "best of month" list
  from a human expert would be caught
- **The 5-10% miss** would be: papers from entirely new domains
  that have no keyword or conceptual overlap with existing work,
  or papers from orgs not in our institution list (rare for impactful work)
- **False positives** (papers that look relevant but aren't) are
  handled by Claude's curation step — that's the whole point of
  having AI judgment in the loop

## What Would Make This 99%?
- Add Papers With Code API (tracks which papers have code releases)
- Add Twitter/X social signals (what researchers are discussing)
- But both add fragility. The 3-layer approach is robust and sufficient.
