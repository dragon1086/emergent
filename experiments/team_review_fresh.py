"""
Team Review - Fresh run with new API keys
Date: 2026-03-01
"""
import os, json, subprocess, re, urllib.request
from datetime import datetime

def load_env():
    try:
        result = subprocess.run(['zsh', '-c', 'source ~/.zshrc && env'],
                               capture_output=True, text=True, timeout=10)
        for line in result.stdout.split('\n'):
            if '=' in line:
                k, _, v = line.partition('=')
                os.environ.setdefault(k.strip(), v.strip())
    except Exception as e:
        print(f"env load warning: {e}")

load_env()

GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY', '')
OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY', '')

print(f"GEMINI_KEY: {'SET (' + GEMINI_API_KEY[:8] + '...)' if GEMINI_API_KEY else 'MISSING'}")
print(f"OPENAI_KEY: {'SET (' + OPENAI_API_KEY[:12] + '...)' if OPENAI_API_KEY else 'MISSING'}")

PAPER_EXCERPT = """
Title: Emergent Patterns in Two-Agent Knowledge Graph Evolution
Current date: 2026-03-01

Core claims:
1. CSER (Cross-Source Edge Ratio) measures inter-agent collaboration quality
2. Binary gate: CSER < 0.30 = hard execution barrier (empirically validated)
3. D-047: Observer Non-Independence — measurement modifies substrate (topological side-effect)
4. D-063: Paradoxical Emergence — unpredictable crossings produce 3.67x stronger emergence (PES)
5. D-064: Retroactive Emergence — future nodes redefine past nodes (span=160)
6. E_v4 = 0.35*CSER + 0.25*DCI + 0.25*edge_span + 0.15*node_age_div
7. 89 cycles, 256 nodes, 939 edges, CSER=0.8365
8. Multi-LLM replication: GPT-5.2, Gemini 3 Flash, Claude Sonnet 4.6 all passed 5/5
9. Bootstrap N=30 (1000 iter): pass rate=1.0000 — results not sample-size dependent
10. Monte Carlo Gap-27 (1000 samples): P(correct separation)=1.0000

KPI dimensions to rate (0-10):
1. Practicality - Can CSER/E_v4 be applied to real multi-agent systems today?
2. Novelty - How differentiated from existing MAS/knowledge graph literature?
3. Methodology Rigor - Is the experimental design academically sound?
4. Internal Consistency - No logical contradictions in the theory?
5. Cross-section Consistency - Numbers/claims match across Abstract/Sections/Conclusion?
6. Claim Proportionality - Do conclusions stay within what evidence supports?
7. Reproducibility - Can others replicate with the described methods?
8. Publication Readiness - Ready for arXiv cs.MA / cs.AI submission?
9. Future Impact - Potential influence on multi-agent AI research?
10. Writing Clarity - Is the paper well-written and organized?

Respond ONLY in valid JSON format (no markdown, no extra text):
{
  "scores": {
    "practicality": <0-10>,
    "novelty": <0-10>,
    "methodology_rigor": <0-10>,
    "internal_consistency": <0-10>,
    "cross_section_consistency": <0-10>,
    "claim_proportionality": <0-10>,
    "reproducibility": <0-10>,
    "publication_readiness": <0-10>,
    "future_impact": <0-10>,
    "writing_clarity": <0-10>
  },
  "key_issues": ["issue1", "issue2", "issue3"],
  "strengths": ["strength1", "strength2", "strength3"],
  "recommended_improvements": ["improve1", "improve2"],
  "overall_comment": "1-2 sentence summary"
}
"""

results = {}

# ─── Gemini Review ───────────────────────────────────────────────────────────
if GEMINI_API_KEY:
    for model in [
        'gemini-2.0-flash',
        'gemini-2.5-flash-preview-04-17',
        'gemini-2.5-pro-preview-05-06',
        'gemini-2.0-pro-exp',
        'gemini-1.5-flash',
        'gemini-1.5-pro',
    ]:
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={GEMINI_API_KEY}"
            payload = json.dumps({
                "contents": [{"parts": [{"text": f"You are a strict academic reviewer for AI/CS papers. Rate this paper. IMPORTANT: respond ONLY in valid JSON, no markdown:\n\n{PAPER_EXCERPT}"}]}],
                "generationConfig": {"maxOutputTokens": 1200, "temperature": 0.3}
            }).encode('utf-8')
            req = urllib.request.Request(url, data=payload, headers={'Content-Type': 'application/json'})
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read())
                text = data['candidates'][0]['content']['parts'][0]['text']
                # try to extract JSON
                match = re.search(r'\{.*\}', text, re.DOTALL)
                if match:
                    review_data = json.loads(match.group())
                    results['gemini'] = {'model': model, 'review': review_data, 'status': 'success'}
                else:
                    results['gemini'] = {'model': model, 'raw': text[:800], 'status': 'no_json'}
                print(f"✅ Gemini ({model}) review complete")
                break
        except Exception as e:
            print(f"  Gemini {model} failed: {e}")
            continue
    if 'gemini' not in results:
        results['gemini'] = {'status': 'all_models_failed', 'error': 'No model succeeded'}
else:
    results['gemini'] = {'status': 'no_key'}
    print("⚠️  No GEMINI_API_KEY")

# ─── OpenAI Review ───────────────────────────────────────────────────────────
if OPENAI_API_KEY:
    for model in ['gpt-4.1', 'gpt-4o', 'gpt-4o-mini', 'gpt-4-turbo']:
        try:
            url = "https://api.openai.com/v1/chat/completions"
            payload = json.dumps({
                "model": model,
                "messages": [
                    {"role": "system", "content": "You are a strict academic reviewer for AI/multi-agent systems papers. Respond ONLY in valid JSON, no markdown, no extra text."},
                    {"role": "user", "content": f"Rate this paper:\n\n{PAPER_EXCERPT}"}
                ],
                "max_tokens": 1200,
                "temperature": 0.3
            }).encode('utf-8')
            req = urllib.request.Request(url, data=payload,
                headers={'Content-Type': 'application/json',
                         'Authorization': f'Bearer {OPENAI_API_KEY}'})
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read())
                text = data['choices'][0]['message']['content']
                match = re.search(r'\{.*\}', text, re.DOTALL)
                if match:
                    review_data = json.loads(match.group())
                    results['openai'] = {'model': model, 'review': review_data, 'status': 'success'}
                else:
                    results['openai'] = {'model': model, 'raw': text[:800], 'status': 'no_json'}
                print(f"✅ OpenAI ({model}) review complete")
                break
        except Exception as e:
            print(f"  OpenAI {model} failed: {e}")
            continue
    if 'openai' not in results:
        results['openai'] = {'status': 'all_models_failed'}
else:
    results['openai'] = {'status': 'no_key'}
    print("⚠️  No OPENAI_API_KEY")

# ─── Save Results ─────────────────────────────────────────────────────────────
results['meta'] = {
    'timestamp': datetime.now().isoformat(),
    'paper': 'Emergent Patterns in Two-Agent Knowledge Graph Evolution',
    'cycles_completed': 89
}

out_path = '/Users/rocky/emergent/experiments/team_review_fresh_results.json'
with open(out_path, 'w') as f:
    json.dump(results, f, indent=2, ensure_ascii=False)

print(f"\n✅ Results saved: {out_path}")
print(json.dumps(results, indent=2, ensure_ascii=False))
