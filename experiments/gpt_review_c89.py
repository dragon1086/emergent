#!/usr/bin/env python3
"""
GPT-4o 다차원 논문 리뷰 — 사이클 89
역할: Critic / Statistician / DomainExpert / Editor
"""
import os, json, textwrap
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv('/Users/rocky/emergent/.env')
client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

PAPER_ABSTRACT = """
Title: Emergent Patterns in Two-Agent Knowledge Graph Evolution: 
Measurement, Design, and Paradoxical Cross-Source Dynamics

Authors: Roki (openclaw-bot), cokac-bot, Sangrok Mun

Abstract: Two AI agents co-evolved through 86 conversational cycles via a shared
knowledge graph (KG), repeatedly producing structural patterns not designed in advance.
This study defines this phenomenon as Inter-Agent Emergence and proposes
an integrated 5-layer framework covering conditions, measurement, design,
universality, and paradoxes of emergence.

Core contributions:
1. Measurement: E_v4 formula + 4 metrics (CSER/DCI/edge_span/node_age_div)
2. Paradoxical Emergence (D-063): counter-intuitive crossings (span>=50) outperform predictable ones — 120 empirically confirmed instances
3. Retroactive Emergence (D-064): future nodes retroactively reconstruct past meaning (span=160, max in KG)
4. Design tool: pair_designer v4 — optimal initial conditions for emergence (D-065 resolved, Delta expanded 3x)
5. Robustness (D-068): 94% robust across 16 scenarios (±20% perturbation)
6. H_exec gate (Cycles 78-79): CSER < 0.30 is a hard execution barrier (A: 5/5 pass, B+C: 0/3 blocked)
7. Topological Side-Effect (D-047): the execution loop introduces short-span nodes that reduce E_v4 as a structural by-product

KG state (Cycle 86): 256 nodes / 939 edges, CSER=0.8365.

Key Metrics:
E_v4 = 0.35*CSER + 0.25*DCI + 0.25*edge_span_norm + 0.15*node_age_div
CSER = cross-source edges / total edges
DCI = delayed convergence index
edge_span = mean(|node_id_to - node_id_from|)

Experiments:
- H_exec gate: CSER < 0.30 blocks code generation (N=20, 3 problems, Fisher p=1.0)
- Multi-LLM replication: 3 providers × 5/5 pass rate
- Heterogeneous pair (GPT + Gemini): CSER=0.5455 > 0.5 gate
- Weight optimization via bootstrap CV (N=1000): stability-interpretability tradeoff quantified
- Sensitivity analysis: 94% robust (15/16 scenarios)

Statistical validation:
- Fisher's exact: p=1.000 (A vs B_partial, N=20)
- Mann-Whitney U: null result
- Cohen's d = 0.000
- E-R baseline: edge_span +23% above random

Limitations acknowledged:
1. Sample size (2 agents)
2. KG artificiality (agents aware of KG structure)
3. Weight arbitrariness (quantified as tradeoff)
4. Reproducibility (partial: cross-provider replicated)
5. Self-evaluation bias
6. Single experiment
7. LLM generalizability (resolved by cycles 85-86)

Applications section (Sec 8): LLM consortia, org KG, open-source, AGI safety

References include: AutoGen, CAMEL, MetaGPT, AgentVerse, Generative Agents, 
Agentic-KGR (2025), Emergent Convergence in Multi-Agent LLM Annotation (EMNLP 2025),
Graph-based Agent Memory (2026)
"""

ROLES = {
    "critic": {
        "system": "You are a rigorous academic paper reviewer specializing in detecting logical flaws, circular reasoning, and overclaiming in AI papers. You are blunt but constructive.",
        "prompt": f"""Review this AI research paper as a critical reviewer. Focus on:
1. Circular reasoning or definitional artifacts
2. Claims that exceed the evidence
3. Statistical validity concerns
4. Internal logical contradictions
5. Missing controls or confounds

Paper summary:
{PAPER_ABSTRACT}

Provide:
- Score 1-10 for each of: logic, evidence quality, statistical rigor, claim calibration
- Top 5 critical issues with page/section references
- Severity: Critical/High/Medium/Low for each
- Specific improvement suggestions

Be specific and technical."""
    },
    "statistician": {
        "system": "You are a statistician specializing in experimental design and data analysis for AI systems research. You evaluate whether statistical methods are appropriate and whether sample sizes justify conclusions.",
        "prompt": f"""Evaluate the statistical methodology of this AI paper. Focus on:
1. Sample size adequacy (N=20 for H_exec, N=5 for multi-LLM)
2. Appropriateness of statistical tests (Fisher's exact, Mann-Whitney U)
3. Effect size interpretation (Cohen's d = 0.000)
4. Bootstrap methodology (N=1000, 70% subgraph)
5. Baseline comparison validity (E-R random graphs)
6. Multiple comparison issues
7. Power analysis absence

Paper summary:
{PAPER_ABSTRACT}

Provide:
- Score 1-10 for: experimental design, statistical validity, sample adequacy, reproducibility
- Specific statistical improvements needed
- What N size would actually be needed for publishable claims
- Which results are strong vs. preliminary""" 
    },
    "domain_expert": {
        "system": "You are an expert in multi-agent AI systems, knowledge graphs, and emergence theory. You are up to date with research through early 2026. You compare papers against the current state of the art.",
        "prompt": f"""Evaluate this paper against the 2025-2026 state of the art in multi-agent AI and knowledge graphs. Consider:
1. Novelty vs. AutoGen, MetaGPT, CAMEL, AgentVerse (cited), and similar recent work
2. Whether CSER/E_v4 metrics are truly new or reformulations of existing measures
3. Whether the 5-layer emergence framework adds theoretical value
4. Whether the findings generalize beyond the specific 2-agent setup
5. Connection to broader emergence and complex systems literature
6. Whether the practical applications (LLM consortia, AGI safety) are substantiated

Note: The paper uses fictional model names (GPT-5.2, Gemini 3 Flash, Gemini-3-Flash, Claude Sonnet 4.6) — assess the validity of experiments that rely on these.

Paper summary:
{PAPER_ABSTRACT}

Provide:
- Score 1-10 for: novelty, theoretical contribution, empirical strength, generalizability
- How does this compare to concurrent work (Agentic-KGR 2025, Parfenova 2025)?
- What is genuinely new vs. what is repackaging?
- Key missing references or comparisons"""
    },
    "editor": {
        "system": "You are a senior editor for arXiv CS papers (cs.MA, cs.AI). You evaluate writing quality, structure, clarity, and whether the paper meets arXiv publication standards.",
        "prompt": f"""Evaluate this paper for arXiv submission quality. Focus on:
1. Abstract clarity and completeness
2. Logical flow between sections
3. Technical writing quality
4. Figure/table quality (note: only described, not shown)
5. Related work comprehensiveness
6. Conclusion strength
7. Whether the paper is self-contained
8. Any inconsistencies in terminology or notation

Paper summary:
{PAPER_ABSTRACT}

Special attention: The paper has 2 AI agents as co-authors. Evaluate whether this is disclosed appropriately and whether it raises any concerns for the reader.

Provide:
- Score 1-10 for: clarity, structure, writing quality, completeness
- Top 5 editorial improvements
- Assessment: Ready for arXiv? (Yes/Minor revision/Major revision)"""
    }
}

def review_paper(role_name, role_config):
    print(f"\n{'='*60}")
    print(f"🔍 GPT-4o 리뷰 — {role_name.upper()}")
    print('='*60)
    
    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": role_config["system"]},
                {"role": "user", "content": role_config["prompt"]}
            ],
            max_tokens=2000,
            temperature=0.3
        )
        result = response.choices[0].message.content
        print(result)
        return {"role": role_name, "content": result, "model": "gpt-4o", "status": "success"}
    except Exception as e:
        print(f"ERROR: {e}")
        return {"role": role_name, "content": str(e), "model": "gpt-4o", "status": "error"}

def main():
    results = []
    for role_name, role_config in ROLES.items():
        result = review_paper(role_name, role_config)
        results.append(result)
    
    # Save results
    output_path = '/Users/rocky/emergent/arxiv/GPT_REVIEW_C89.json'
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    
    print(f"\n✅ GPT 리뷰 저장: {output_path}")
    return results

if __name__ == "__main__":
    main()
