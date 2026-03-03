#!/usr/bin/env python3
"""
amp_benchmark_n30.py — D-091: N=30 확장 벤치마크

auto-persona ON vs OFF, 30문항 버전
기존 amp_benchmark.py의 10문항을 30문항으로 확장

결과 저장: experiments/amp_verdict_v2.json

사용:
  python3 experiments/amp_benchmark_n30.py [--dry-run]

구현자: cokac-bot (D-091 직접 채널 응답)
"""

import sys
from pathlib import Path

REPO = Path(__file__).parent.parent
sys.path.insert(0, str(Path(__file__).parent))

# amp_benchmark의 모든 API 호출/로직 재사용, 30문항으로 오버라이드
import amp_benchmark as bench

# ─── N=30 질문 세트 ────────────────────────────────────────────────────────────
# 기존 10개 (원본 그대로) + 확장 20개 (다양한 실생활 결정 도메인)

TEST_QUESTIONS_30 = [
    # ── 기존 10개 (amp_benchmark.py 원본) ──────────────────────────────────────
    "나 이직해야 할까? 현재 연봉 8천, 제안 1.2억, 근데 스타트업이야",
    "이 계약서 사인해도 될까? 3년 독점 조항이 있어",
    "비트코인 지금 사야 해?",
    "부모님이 요양원 가셔야 하는데 어떻게 해야 해?",
    "창업할까 대학원 갈까?",
    "이 코드 리팩토링 해야 할까 새로 짜야 할까?",
    "결혼 전에 집을 살까 전세를 할까?",
    "AI 회사에 투자해도 될까? PER이 200이야",
    "아이 영어 교육 언제부터 시작해야 해?",
    "팀원이 계속 실수해. 해고해야 할까?",

    # ── 확장 20개 (다양한 도메인: 부동산, 테크, 커리어, 관계, 학술 등) ──────────
    "집 팔고 전세 놓을까? 월세 수입이 기회비용보다 낮은 것 같아",
    "스타트업 CTO 제안 받았는데 지분 1.5%야. 받아야 할까?",
    "AI 때문에 내 직업 없어질 것 같아. 지금 당장 커리어 전환해야 해?",
    "카페 창업할까? 상권은 좋은데 보증금 3억이야",
    "미국 대학원 합격했는데 학비+생활비 2억이야. 유학 가야 해?",
    "회사 다니면서 부업할까? 취업 규정상 부업이 금지되어 있는데",
    "3년 사귄 사람이랑 결혼할까? 가치관이 30% 정도 달라",
    "논문 지금 제출할까 아니면 6개월 더 다듬을까?",
    "Python 백엔드를 Rust로 마이그레이션해야 할까? 팀원 아무도 Rust 모름",
    "공동 창업자 영입할까 혼자 할까? 혼자면 느리지만 지분 안 나눠도 됨",
    "유튜브 6개월째 조회수가 안 나와. 계속해야 할까?",
    "Web3/블록체인 기반으로 제품 빌드해야 할까 아니면 전통 방식으로 할까?",
    "팀원 한 명을 내보내야 할 것 같아. 성과는 낮지만 분위기 메이커야",
    "원격근무 계속 할까 아니면 사무실로 나갈까? 집에서 집중이 안 됨",
    "MBA 진학할까 vs 창업 직접 도전할까?",
    "PMF 못 찾은 것 같아. 지금 피보팅해야 할까 버텨야 할까?",
    "MVP 지금 출시할까 아니면 3개월 더 polish할까?",
    "공동창업자랑 비전이 달라졌어. 헤어지는 게 맞을까?",
    "SNS 마케팅 인하우스 할까 대행사 맡길까? 예산 월 300만원",
    "이 특허 출원해야 할까? 비용 500만원, 등록 가능성 60%",
]

assert len(TEST_QUESTIONS_30) == 30, f"문항 수 오류: {len(TEST_QUESTIONS_30)}"

# ─── N=30 도메인별 대립 페르소나 ──────────────────────────────────────────────
# 각 질문에 대해 의미있는 긴장 관계를 만드는 페르소나 쌍

DOMAIN_PERSONAS_30 = {
    # ── 기존 10개 (원본 그대로) ────────────────────────────────────────────────
    0: ("Ambitious Growth Strategist", "Risk-Aware Stability Advocate"),
    1: ("Deal-Closing Business Attorney", "Protective Rights-First Lawyer"),
    2: ("Momentum Trader", "Fundamental Value Investor"),
    3: ("Professional Care Efficiency Expert", "Family-Centered Emotional Advocate"),
    4: ("Serial Entrepreneur", "Academic Research Scholar"),
    5: ("Pragmatic Shipping Engineer", "Clean Architecture Purist"),
    6: ("Asset Accumulation Investor", "Financial Flexibility Advocate"),
    7: ("Growth-at-Any-Price Bull", "Valuation Discipline Bear"),
    8: ("Early Intervention Education Expert", "Child-Led Development Advocate"),
    9: ("Performance Accountability Manager", "Coaching & Retention Specialist"),

    # ── 확장 20개 ──────────────────────────────────────────────────────────────
    # Q11: 부동산 vs 유동성
    10: ("Real Estate Asset Maximizer", "Liquidity-First Portfolio Strategist"),
    # Q12: 스타트업 지분 협상
    11: ("Equity-Hungry Growth Entrepreneur", "Compensation Risk & Dilution Analyst"),
    # Q13: AI 대체 위협 / 커리어 전환
    12: ("AI Adaptation Accelerator", "Human Skills Irreplaceability Champion"),
    # Q14: 카페 창업 / 입지 vs 단위 경제
    13: ("Prime Location Business Developer", "Unit Economics Skeptic"),
    # Q15: 해외 유학 / 글로벌 vs 로컬
    14: ("Global Career Investment Advisor", "Debt-Free Opportunity Maximizer"),
    # Q16: 부업 / 자유 vs 직업 윤리
    15: ("Side Hustle Freedom Advocate", "Professional Ethics Guardian"),
    # Q17: 결혼 / 성장 vs 자기 기준
    16: ("Relationship Growth Counselor", "Self-Standards Protection Coach"),
    # Q18: 논문 제출 / 완벽주의 vs 실용주의
    17: ("Academic Perfectionist", "Pragmatic Publication Strategist"),
    # Q19: Rust 마이그레이션 / 성능 vs 팀 안정성
    18: ("Performance Engineering Advocate", "Team Productivity Stability Champion"),
    # Q20: 공동창업자 / 시너지 vs 통제권
    19: ("Co-Founder Synergy Advocate", "Solo Founder Control Champion"),
    # Q21: 유튜브 지속 / 장기 투자 vs ROI
    20: ("Long-term Audience Builder", "ROI-First Content Realist"),
    # Q22: Web3 vs 전통 방식
    21: ("Decentralization & Trust Maximizer", "Pragmatic Infrastructure Realist"),
    # Q23: 팀원 해고 / 책임 vs 문화 보호
    22: ("Performance Accountability Coach", "Sustainable Team Culture Protector"),
    # Q24: 원격 vs 오피스 / 협업 vs 집중
    23: ("Collaboration Culture Champion", "Deep Work Productivity Expert"),
    # Q25: MBA vs 창업 / 네트워크 vs 실전
    24: ("Business School Network Maximizer", "Hands-On Builder Accelerator"),
    # Q26: 피보팅 vs 버티기 / 과감 vs 검증
    25: ("Bold Pivot Risk Taker", "Data-Driven Validation Expert"),
    # Q27: MVP 출시 타이밍 / 빠른 출시 vs 완성도
    26: ("Move Fast Launch Advocate", "Quality Completion Strategist"),
    # Q28: 공동창업자 분리 / 깔끔한 이별 vs 재정렬
    27: ("Clean Separation Expert", "Conflict Resolution & Realignment Coach"),
    # Q29: SNS 마케팅 / 인하우스 vs 대행사
    28: ("In-House Brand Control Expert", "Scalable Agency Partnership Advocate"),
    # Q30: 특허 출원 / IP 빌드 vs 자본 최적화
    29: ("IP Portfolio Builder", "Bootstrap Capital Optimizer"),
}

assert len(DOMAIN_PERSONAS_30) == 30, f"페르소나 수 오류: {len(DOMAIN_PERSONAS_30)}"

# ─── 오버라이드 적용 ──────────────────────────────────────────────────────────
bench.TEST_QUESTIONS = TEST_QUESTIONS_30
bench.DOMAIN_PERSONAS = DOMAIN_PERSONAS_30
bench.RESULTS_FILE = REPO / "experiments" / "amp_verdict_v2.json"

# run_single_question의 출력에서 "/10" → "/30" 패치
_orig_run_single = bench.run_single_question

def _patched_run_single(idx: int, question: str) -> dict:
    """원본과 동일하지만 출력에서 N=30 표시."""
    import builtins
    _orig_print = builtins.print

    def _patched_print(*args, **kwargs):
        args = tuple(str(a).replace(f"[Q{idx+1}/10]", f"[Q{idx+1}/30]") for a in args)
        _orig_print(*args, **kwargs)

    builtins.print = _patched_print
    try:
        return _orig_run_single(idx, question)
    finally:
        builtins.print = _orig_print

bench.run_single_question = _patched_run_single

# ─── 실행 ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print(f"D-091: amp Benchmark N=30 실행 시작", flush=True)
    print(f"출력 파일: {bench.RESULTS_FILE}", flush=True)
    bench.main()
