# Track 3: smarter cut creation with an LLM

**Question:** can an LLM understand the thought flow of a source well enough to propose better cuts than keyword
or meaning search plus sentence snapping? This includes cuts for a documentary that braids several people's stories
around a concept (your first P19 message).

**Short answer: yes, with a specific division of labour.** The LLM judges content and structure and picks spans by
**line IDs**. The machine owns time: snapping, pauses, lengths. This is where research and the products that work
have converged.

## 1. Where Recomposer is today

- `cut suggest "<query>"`: lexical or semantic hits widened to whole thoughts. Sentence ends and pauses, min/max
  length, no overlap.
- `search --semantic`: e5-small windows.
- `topic scan`: passages scored by key-term density.
- `journey from-topic`: sections per creator or per hand-typed stance.
- `edit/snap.py`: boundary snapping.
- **Judgement** (is this self-contained, is it the best telling, does it set up or pay off another cut) is left to
  the agent reading raw transcripts, with no shared structure and no memory between sessions.

## 2. Literature and products

| Work | What it does | Lesson for us |
|---|---|---|
| **RankCut** (IUI 2026, Hamburg) | LLM: overview summary → plain-language selection rules → rule-conditioned ranking of small transcript windows; deterministic, duration-safe selector in source order; markers with confidence for the editor. Beat extractive baselines on MeetingBank; editors found it faster. | Split *understanding* (summary, rules) from *ranking* (small windows). Keep assembly deterministic. Show scores and reasons. |
| **highlightr** (open source, 2025) | Overlapping windows → LLM candidates → global re-rank. Clips are scored on interestingness, self-contained, boundary quality, topic relevance and recovery confidence. "The LLM never sets timing": boundaries come from transcript row IDs. | The same rule for us: the LLM returns `S3.seg 412..431`, never seconds. |
| **Prompt-driven agentic editing** (arXiv 2509.16811, 2025; 400+ videos, expert ratings) | Builds a persistent semantic index: hierarchical temporal segmentation, scratchpad memory compression, fusion of summaries with timestamped traces. Agents plan narration, retrieve clips and render. | Long sources need a **hierarchical index built once**, not whole transcripts in context. Reason freely first, then a second call writes the structured output. |
| ButterCut, ClaudeCut, Doza Assist, Selects, EditAssist (2025–26 products) | Claude/LLM as the "brain" over word-timed transcripts. Selects, string-outs, paper edit → timeline (FCPXML/EDL). Thematic and narrative modes. | The market shape matches Recomposer (agent plus verbs). Editors want explained selects and a paper edit, not a finished cut. |
| Topic segmentation studies (YTSeg EACL 2024; TreeSeg 2024; ToC LoRA, Interspeech 2025; paragraph segmentation 2025) | Zero-shot LLM boundaries agree only moderately with human chapters (F1 ~10–40 depending on corpus). LoRA fine-tuning plus pause features gives the best scores. Embedding-based hierarchical clustering (TreeSeg) is a strong cheap baseline. | Do not rely on zero-shot LLM boundaries alone. Combine embedding segmentation, pause cues and LLM judgement. Your accept/reject log is the future fine-tuning data. |

## 3. The design this points to

1. **Index once per source** (cheap model plus machine features):
   - Thought units from word timings and pauses (shared with Track 1's frame).
   - Speaker turns.
   - Embedding windows (exist).
   - A hierarchy of chapter → section → unit (TreeSeg-style divisive clustering, or creator chapters where they
     exist).
2. **Understand** (LLM, per section, cached): a short card per unit with fields:
   - kind: story / claim / explanation / question / emotion / joke
   - who
   - stance
   - concepts
   - self-contained? (needs what context)
   - hook strength
   - quotability
   - set-up/pay-off links to other units
3. **Select** (LLM over cards, not raw text) for a goal ("concept X across people", "Shorts on Y"). Return unit IDs
   with reasons.
4. **Place** (machine): snap to unit boundaries and pauses (`snap.py`), apply length goals, check overlaps.
5. **Assemble** (LLM plus machine): a paper edit with acts (theme, braided stories, debate, timeline), then a
   journey with sections. A flow check scores adjacent cuts: question → answer, callbacks, speaker variety, nobody
   absent too long.
6. **Learn** from you: every accepted, trimmed or rejected candidate is logged. These are the evaluation metric and
   later the preference data.

## 4. Feasibility

| Part | Feasible | Notes |
|---|---|---|
| Unit cards (understanding) | high | Bounded tokens if done per section. The cost is one pass per source, reused by every journey. |
| Selection by IDs with reasons | high | The proven pattern. Removes timing hallucination. |
| Boundary quality | high | Existing snapping plus unit boundaries from word timings. |
| Cross-source concept map | medium-high | Embeddings cluster, the LLM names and merges clusters. Multilingual sources work through e5 (a larger model for am/om queries is a known backlog item). |
| Narrative structure (documentary arcs) | medium | LLMs propose plausible paper edits. Quality is subjective, so it needs your review loop. |
| Evaluation | the hard part | No ground truth. Use your accept rate, seconds trimmed per accepted cut, and blind comparisons. |

## 5. Experiment to decide (go/no-go)

On alex-oconnor (consciousness) and ai-and-ideas (AI models):

1. Generate 20 candidates for 3 goals each with:
   - (a) today's `cut suggest` + semantic search
   - (b) unit cards + LLM selection
   - (c) your own cuts already made in those projects, as a reference
2. Blind-rate candidates: keep / trim / reject. Record the seconds trimmed and the "needs context" flags.

**Go if** (b) gets a higher keep rate than (a) and needs less trimming. Then build the index plus cards as the shared
understanding layer with Track 1.
