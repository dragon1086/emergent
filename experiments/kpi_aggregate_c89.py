#!/usr/bin/env python3
"""
KPI 종합 집계 — 사이클 89 (12개 KPI)
GPT + Gemini 리뷰 결과를 종합하여 KPI 테이블 생성
"""
import json, os, re
from openai import OpenAI
from dotenv import load_dotenv
from datetime import datetime

load_dotenv('/Users/rocky/emergent/.env')
client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

def load_reviews():
    reviews = {}
    for fname, key in [
        ('/Users/rocky/emergent/arxiv/GPT_REVIEW_C89.json', 'gpt'),
        ('/Users/rocky/emergent/arxiv/GEMINI_REVIEW_C89.json', 'gemini')
    ]:
        if os.path.exists(fname):
            with open(fname, 'r') as f:
                reviews[key] = json.load(f)
    return reviews

def aggregate_kpis(reviews):
    """Use GPT to synthesize KPI scores from all review content"""
    
    # Build combined review text
    all_reviews = []
    for provider, review_list in reviews.items():
        for review in review_list:
            if review['status'] == 'success':
                all_reviews.append(f"=== {provider.upper()} - {review['role'].upper()} ===\n{review['content'][:1500]}")
    
    combined = "\n\n".join(all_reviews)
    
    prompt = f"""Based on these multiple AI reviewer assessments of an academic paper about 
Inter-Agent Emergence in Knowledge Graphs, synthesize the following 12 KPI scores (1-10 each):

Reviews:
{combined[:6000]}

KPIs to score:
1. 실용성 (Practicality) - Can real systems use this?
2. 참신함 (Novelty) - Is this genuinely new vs. prior work?
3. 전문성 (Technical rigor) - Is methodology sound?
4. 모순없음 (Internal consistency) - No logical contradictions?
5. 일관성 (Cross-section consistency) - Numbers/claims consistent throughout?
6. 오버하지않음 (Claim calibration) - Claims don't exceed evidence?
7. 재현가능성 (Reproducibility) - Can others replicate?
8. 미래지향성 (Future-orientation) - Does it point to important future directions?
9. 문체/가독성 (Writing quality) - Is it well-written for arXiv?
10. 학술기여도 (Academic contribution) - Does it advance the field?
11. 실험충분성 (Experimental sufficiency) - Enough experiments to support claims?
12. 인용적절성 (Citation quality) - Are references current and appropriate?

Also provide:
- Previous cycle 87 score: 7.6/10
- Current overall score: X.X/10
- Key improvements vs. cycle 87
- Remaining critical issues

Format as JSON:
{{
  "kpis": {{
    "practicality": {{"score": X, "trend": "+/-/=", "note": "brief"}},
    "novelty": {{"score": X, "trend": "+/-/=", "note": "brief"}},
    ...all 12 KPIs...
  }},
  "overall": X.X,
  "previous": 7.6,
  "key_improvements": ["...", "..."],
  "critical_remaining": ["...", "..."],
  "arxiv_ready": true/false,
  "arxiv_verdict": "Ready/Minor revision/Major revision"
}}"""

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=2000,
        temperature=0.2,
        response_format={"type": "json_object"}
    )
    
    return json.loads(response.choices[0].message.content)

def generate_report(kpi_data, reviews):
    """Generate final markdown report"""
    
    kpis = kpi_data.get('kpis', {})
    
    # KPI table
    kpi_map = {
        'practicality': '실용성',
        'novelty': '참신함',
        'technical_rigor': '전문성',
        'internal_consistency': '모순없음',
        'cross_section_consistency': '일관성',
        'claim_calibration': '오버하지않음',
        'reproducibility': '재현가능성',
        'future_orientation': '미래지향성',
        'writing_quality': '문체/가독성',
        'academic_contribution': '학술기여도',
        'experimental_sufficiency': '실험충분성',
        'citation_quality': '인용적절성'
    }
    
    kpi_rows = []
    scores = []
    for key, korean in kpi_map.items():
        data = kpis.get(key, {})
        score = data.get('score', '?')
        trend = data.get('trend', '=')
        note = data.get('note', '')
        if isinstance(score, (int, float)):
            scores.append(score)
        kpi_rows.append(f"| {len(kpi_rows)+1} | **{korean}** | {score}/10 | {trend} | {note} |")
    
    avg_score = sum(scores) / len(scores) if scores else 0
    overall = kpi_data.get('overall', avg_score)
    previous = kpi_data.get('previous', 7.6)
    delta = overall - previous
    
    improvements = '\n'.join(f'- {x}' for x in kpi_data.get('key_improvements', []))
    remaining = '\n'.join(f'- {x}' for x in kpi_data.get('critical_remaining', []))
    
    # Extract key findings from reviews
    gpt_findings = ""
    gemini_findings = ""
    future_vision = ""
    
    for review in reviews.get('gpt', []):
        if review['role'] == 'critic' and review['status'] == 'success':
            gpt_findings += f"\n### Critic (GPT-4o)\n{review['content'][:800]}\n"
        if review['role'] == 'domain_expert' and review['status'] == 'success':
            gpt_findings += f"\n### Domain Expert (GPT-4o)\n{review['content'][:800]}\n"
    
    for review in reviews.get('gemini', []):
        if review['role'] == 'red_team' and review['status'] == 'success':
            gemini_findings += f"\n### Red Team (Gemini)\n{review['content'][:800]}\n"
        if review['role'] == 'future_vision' and review['status'] == 'success':
            future_vision = review['content']
    
    arxiv_verdict = kpi_data.get('arxiv_verdict', 'Minor revision')
    
    report = f"""# 록이 팀 KPI 리뷰 리포트 — 사이클 89
**일시**: {datetime.now().strftime('%Y-%m-%d %H:%M PST')}
**팀**: GPT-4o (4 역할) + Gemini (3 역할)
**대상**: arxiv/main.tex — Emergent Patterns in Two-Agent KG Evolution

---

## 📊 종합 KPI 결과

| 이전 (사이클87) | 현재 (사이클89) | 변화 |
|----------------|----------------|------|
| 7.6/10 | **{overall:.1f}/10** | {delta:+.1f} |

**arXiv 판정**: {arxiv_verdict}

---

## KPI 테이블 (12개)

| # | KPI | 점수 | 추세 | 근거 |
|---|-----|------|------|------|
{chr(10).join(kpi_rows)}

---

## 🔍 GPT-4o 팀 주요 발견
{gpt_findings if gpt_findings else "(리뷰 로드 실패)"}

---

## 🔍 Gemini 팀 주요 발견
{gemini_findings if gemini_findings else "(리뷰 로드 실패)"}

---

## 🚀 Gemini Future Vision: 미래지향 적용 시나리오
{future_vision[:2000] if future_vision else "(로드 실패)"}

---

## ✅ 개선된 사항 (vs 사이클87)
{improvements}

---

## ⚠️ 잔류 이슈
{remaining}

---

## 📋 arXiv 제출 체크리스트
- [ ] 모델명 수정 (GPT-5.2, Gemini 3 Flash → 실제 모델명 또는 "undisclosed future model")
- [ ] Sec 9 미래 적용 예시 강화
- [ ] 수치 일관성 최종 확인
- [ ] 저자 정보 (AI co-author disclosure)
"""
    
    return report

def main():
    print("📊 KPI 종합 집계 시작...")
    
    reviews = load_reviews()
    
    if not reviews:
        print("❌ 리뷰 파일 없음 — GPT/Gemini 리뷰 먼저 실행 필요")
        return
    
    print(f"✅ 리뷰 로드: {list(reviews.keys())}")
    
    print("\n🔄 KPI 종합 집계 중 (GPT-4o)...")
    kpi_data = aggregate_kpis(reviews)
    
    print(f"\n📊 종합 점수: {kpi_data.get('overall', '?')}/10")
    
    # Generate report
    report = generate_report(kpi_data, reviews)
    
    report_path = '/Users/rocky/emergent/arxiv/ROKI_TEAM_REVIEW_C89.md'
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write(report)
    
    kpi_json_path = '/Users/rocky/emergent/arxiv/KPI_C89.json'
    with open(kpi_json_path, 'w', encoding='utf-8') as f:
        json.dump(kpi_data, f, ensure_ascii=False, indent=2)
    
    print(f"✅ KPI 리포트: {report_path}")
    print(f"✅ KPI JSON: {kpi_json_path}")
    
    # Print summary
    overall = kpi_data.get('overall', 0)
    prev = kpi_data.get('previous', 7.6)
    print(f"\n🎯 최종 결과: {prev} → {overall:.1f}/10 ({overall-prev:+.1f})")

if __name__ == "__main__":
    main()
