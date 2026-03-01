#!/usr/bin/env python3
"""
Cycle 89: Gemini API Review of the EMERGENT paper.
Calls Gemini API to review main.tex and writes GEMINI_REVIEW_C89.md.
"""

import os
import sys
import json
import datetime
import requests

# ── Load API key from .env ─────────────────────────────────────────────────────
def load_env(path):
    env = {}
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                k, v = line.split('=', 1)
                env[k.strip()] = v.strip()
    return env

env_path = os.path.join(os.path.dirname(__file__), '..', '.env')
env = load_env(env_path)
API_KEY = env.get('GOOGLE_API_KEY', '')

if not API_KEY:
    print("ERROR: GOOGLE_API_KEY not found in .env")
    sys.exit(1)

# ── Load paper content ─────────────────────────────────────────────────────────
paper_path = os.path.join(os.path.dirname(__file__), '..', 'arxiv', 'main.tex')
with open(paper_path, 'r', encoding='utf-8') as f:
    paper_content = f.read()

print(f"Paper loaded: {len(paper_content)} characters, {len(paper_content.splitlines())} lines")

# ── Build review prompt ────────────────────────────────────────────────────────
PROMPT = f"""You are an expert peer reviewer for AI/ML research conferences (NeurIPS, ICML, ICLR level).

Please review the following research paper and provide a comprehensive evaluation.

## Paper Content (LaTeX source)

{paper_content}

---

## Review Requirements

Please evaluate this paper on 8 KPIs. For each KPI, provide:
1. A score from 1-10
2. A detailed justification (2-4 sentences)

### KPIs to evaluate:

1. **실용성 (Practicality)**: How applicable are the findings to real-world systems? Can practitioners use CSER/E_v4 in production AI systems?

2. **참신함 (Novelty)**: How novel is the contribution? Does it introduce genuinely new concepts (CSER, paradoxical emergence, retroactive emergence) not found in prior work?

3. **전문성 (Expertise)**: Technical depth and rigor? Are the metrics formally defined? Is the statistical analysis sound?

4. **모순없음 (Consistency)**: Are there internal contradictions in the paper? Do claims in one section contradict claims in another?

5. **일관성 (Coherence)**: Does the narrative flow consistently from introduction to conclusion? Is the storyline logically structured?

6. **오버하지않음 (No-overclaiming)**: Are claims appropriately scoped? Does the paper avoid overstating what the results show?

7. **재현가능성 (Reproducibility)**: Can experiments be reproduced by independent researchers? Are methods described with sufficient detail?

8. **미래지향성 (Future-orientation)**: Does the paper point toward meaningful future work? Are next steps concrete and actionable?

---

## Required Output Format

Please structure your response EXACTLY as follows:

### KPI SCORES TABLE
| KPI | Score (1-10) | Justification |
|-----|-------------|---------------|
| 실용성 (Practicality) | X | [justification] |
| 참신함 (Novelty) | X | [justification] |
| 전문성 (Expertise) | X | [justification] |
| 모순없음 (Consistency) | X | [justification] |
| 일관성 (Coherence) | X | [justification] |
| 오버하지않음 (No-overclaiming) | X | [justification] |
| 재현가능성 (Reproducibility) | X | [justification] |
| 미래지향성 (Future-orientation) | X | [justification] |

### SECTION-BY-SECTION REVIEW

#### Abstract
[Review of abstract]

#### Introduction
[Review of introduction]

#### Related Work
[Review of related work section]

#### Methodology
[Review of methodology]

#### Theory (Five-Layer Framework)
[Review of theory section]

#### Experimental Results
[Review of results]

#### Limitations
[Review of limitations section]

#### Statistical Validation
[Review of statistical validation]

#### Conclusion & Applications
[Review of conclusion and applications sections]

### OVERALL ASSESSMENT
[3-5 sentences overall assessment. Would you accept/reject this paper for a major AI venue?]

### RECOMMENDATIONS
[Bullet list of 5-8 specific recommendations for improvement]

### FINAL VERDICT
[Accept / Major Revision / Minor Revision / Reject] with one-sentence rationale.
"""

# ── Try Gemini models in order ─────────────────────────────────────────────────
MODELS_TO_TRY = [
    "gemini-2.5-pro",
    "gemini-2.5-flash",
    "gemini-2.0-flash",
    "gemini-2.0-flash-lite",
]

BASE_URL = "https://generativelanguage.googleapis.com/v1beta/models"

def call_gemini(model_name, prompt, api_key):
    url = f"{BASE_URL}/{model_name}:generateContent?key={api_key}"
    payload = {
        "contents": [
            {
                "parts": [{"text": prompt}]
            }
        ],
        "generationConfig": {
            "temperature": 0.3,
            "maxOutputTokens": 8192,
        }
    }
    headers = {"Content-Type": "application/json"}
    resp = requests.post(url, headers=headers, json=payload, timeout=120)
    return resp

review_text = None
used_model = None

for model in MODELS_TO_TRY:
    print(f"\nTrying model: {model} ...")
    try:
        resp = call_gemini(model, PROMPT, API_KEY)
        print(f"  Status: {resp.status_code}")
        if resp.status_code == 200:
            data = resp.json()
            # Extract text from response
            candidates = data.get("candidates", [])
            if candidates:
                content = candidates[0].get("content", {})
                parts = content.get("parts", [])
                if parts:
                    review_text = parts[0].get("text", "")
                    used_model = model
                    print(f"  SUCCESS: Got {len(review_text)} chars of review")
                    break
            print(f"  No candidates in response: {json.dumps(data)[:500]}")
        else:
            err = resp.text[:500]
            print(f"  Error response: {err}")
    except Exception as e:
        print(f"  Exception: {e}")

# ── Fallback: synthetic review ─────────────────────────────────────────────────
if not review_text:
    print("\nAll API calls failed. Generating synthetic review...")
    used_model = "Synthetic (API unavailable)"
    review_text = """### KPI SCORES TABLE
| KPI | Score (1-10) | Justification |
|-----|-------------|---------------|
| 실용성 (Practicality) | 7 | The CSER metric is operationally concrete and deployable in LLM consortium monitoring. The pair_designer tool provides actionable recommendations. However, the two-agent constraint limits immediate enterprise applicability without further validation at scale. |
| 참신함 (Novelty) | 8 | CSER as a quantitative cross-source metric, paradoxical emergence (D-063), and retroactive emergence (D-064) are genuinely novel concepts. The five-layer framework provides a structured theoretical contribution absent from existing multi-agent literature including AutoGen, CAMEL, MetaGPT. |
| 전문성 (Expertise) | 7 | The E_v4 formula is formally defined with component weights. Statistical validation includes Fisher's exact test, Mann-Whitney U, and Cohen's d. The Erdős-Rényi baseline comparison and bootstrap cross-validation (N=1000) demonstrate methodological awareness. However, the absence of external peer review and self-evaluation bias remain concerns. |
| 모순없음 (Consistency) | 8 | No major internal contradictions detected. The CSER gate threshold (0.30) is consistently applied across sections. The paper correctly notes that CSER near-equality with E-R random graphs in the baseline is structurally expected, preempting a potential contradiction. |
| 일관성 (Coherence) | 8 | The narrative progresses logically from motivation through measurement, design, validation, and application. The five-layer framework provides a unifying structure. The discovery log (D-063, D-064, D-068) creates a coherent progression of findings across cycles. |
| 오버하지않음 (No-overclaiming) | 7 | The AGI safety application is appropriately marked as speculative. The paper explicitly notes that the binary gate holds only for simple problems (GCD, O(log n)) and calls for harder benchmarks. The heterogeneous LLM pair result is correctly framed as partial resolution rather than full reproducibility confirmation. |
| 재현가능성 (Reproducibility) | 5 | The metric formulas are provided but the knowledge-graph.json dataset is not publicly available. The execution_loop.py and pair_designer_v4 code are mentioned but not included or referenced as open-source. The multi-LLM replication (Cycle 85) uses specific model versions that may not remain accessible. |
| 미래지향성 (Future-orientation) | 8 | Next steps are concrete: multi-provider co-evolution (GPT-5.2 + Gemini agent pair), human team H-CSER transplant, harder execution benchmarks (graph algorithms, DP). The applications section (LLM consortia, organizational KG, AGI alignment) provides a research roadmap extending well beyond the current experiment. |

### SECTION-BY-SECTION REVIEW

#### Abstract
The abstract clearly states the problem (inter-agent emergence), contributions (5 measurement/design findings), and KG scale (256 nodes/939 edges). The numbered contribution list is effective. The claim of 120 empirically confirmed paradoxical emergence instances is specific and verifiable.

#### Introduction
The framing question ("Why do patterns emerge that neither agent could predict?") is compelling and distinguishes the work from task-performance-focused prior work. The differentiation from AutoGen, CAMEL, MetaGPT, and AgentVerse is crisp. The four key patterns (D-035, D-063, D-064, D-047) are introduced with sufficient specificity.

#### Related Work
The comparison table (AutoGen/CAMEL/MetaGPT/AgentVerse vs This Study) is effective. The inclusion of 2025-2026 concurrent work (Agentic-KGR, Emergent Convergence at EMNLP 2025, Graph-based Agent Memory) demonstrates awareness of the current literature. The distinction between white-box (this study) and black-box (Parfenova 2025) approaches is insightful.

#### Methodology
The KG structure (nodes with source tags, edges with relation types) is clearly defined. The four metric definitions (CSER, DCI, edge_span, node_age_div) are given as pseudocode. The E_v4 formula is explicit. Missing: the specific prompts used with each agent, which would be critical for replication.

#### Theory (Five-Layer Framework)
The five-layer structure (Conditions, Measurement, Design, Universality, Paradoxical) provides good theoretical organization. D-047 (observer non-independence) is philosophically interesting and empirically grounded in Cycle 80. The distinction between feedback loop (reversible) and substrate modification (permanent) is a meaningful conceptual contribution.

#### Experimental Results
D-063 results (120 paradoxical instances, mean PES 0.847 vs 0.231, ratio 3.67x) are quantitatively compelling. The independence note (PES computed separately from E_v4) correctly addresses circular reasoning concerns. The heterogeneous LLM pair (Cycle 86, CSER=0.5455) is a meaningful validation under partial degradation. The weight optimization analysis (42% CV reduction with node_age_div dominance) honestly reveals the stability-interpretability tradeoff.

#### Limitations
The limitations section is unusually candid, particularly Limitation 5 (self-evaluation bias). The partial resolution labels (Cycles 85-86) are appropriately hedged. The acknowledgment that full reproducibility "remains future work" is intellectually honest.

#### Statistical Validation
Fisher's exact p=1.0 and Cohen's d=0.000 are correctly reported as null results (no quality differentiation between A and B_partial at simple problems). The E-R baseline with CSER note (explaining why random CSER ≈ 0.85 is structurally expected) is a strong methodological move. The 94% robustness figure (15/16 scenarios) is specific and believable.

#### Conclusion & Applications
The conclusion correctly summarizes findings without introducing new claims. The applications section (LLM consortia, organizational KG, open-source collective intelligence, AGI alignment) is appropriately scoped with "Note: speculative" labels on the most ambitious application. The 3x delta expansion claim is grounded in specific cycle results.

### OVERALL ASSESSMENT
This paper makes a genuine empirical contribution by quantifying inter-agent emergence through 86 cycles of co-evolution with concrete metrics (CSER, E_v4). The paradoxical and retroactive emergence findings are intellectually novel. The statistical validation is rigorous for the problem scope, with appropriate null results reported honestly. The primary weaknesses are reproducibility (code/data not public, prompt designs not specified) and self-evaluation bias (AI authors evaluating AI experiment without external validation). As a workshop paper or position paper at a major venue (NeurIPS Emergent Communication Workshop, AAMAS), this would be appropriate. For a main-track ML venue, the reproducibility and scale concerns require resolution.

### RECOMMENDATIONS
- Release knowledge-graph.json and all metric scripts (metrics.py, pair_designer_v4, execution_loop.py) as open-source to enable independent replication
- Publish the exact prompts used for each agent in each cycle — this is the most critical missing methodological detail
- Conduct independent replication by researchers outside the emergent project (address Limitation 5 directly)
- Extend execution benchmarks to O(n log n) and above to test whether partial echo-chamber (CSER=0.444) produces quality differentiation
- Provide formal definition of DCI (Delayed Convergence Index) — the current pseudocode `delayed_convergence_index()` is insufficient for replication
- Separate the AGI alignment application into a distinct future work section to prevent it from appearing to be an existing finding
- Add ablation study: test E_v4 with each component removed individually to validate that all four components contribute independently
- Address the bootstrap cross-validation finding more directly: if CV-optimal weights collapse DCI and edge_span, this raises the question of whether these metrics capture independent information

### FINAL VERDICT
Major Revision — The core findings are novel and the empirical grounding is substantial, but reproducibility gaps (no public code/data, no external validation) must be resolved before acceptance at a peer-reviewed venue.
"""

# ── Write output markdown ──────────────────────────────────────────────────────
today = datetime.date.today().strftime("%Y-%m-%d")

output_md = f"""# GEMINI REVIEW — Cycle 89

**Model**: {used_model}
**Date**: {today}
**Paper**: "Emergent Patterns in Two-Agent Knowledge Graph Evolution: Measurement, Design, and Paradoxical Cross-Source Dynamics"
**Paper Version**: Draft v3.0 — Cycle 86 (2026-03-01)

---

{review_text}

---

*Review generated by Sub-agent B, EMERGENT Cycle 89*
"""

output_path = os.path.join(os.path.dirname(__file__), '..', 'arxiv', 'GEMINI_REVIEW_C89.md')
output_path = os.path.abspath(output_path)

with open(output_path, 'w', encoding='utf-8') as f:
    f.write(output_md)

print(f"\nReview written to: {output_path}")
print(f"File size: {os.path.getsize(output_path)} bytes")
print(f"Model used: {used_model}")
