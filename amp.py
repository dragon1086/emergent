#!/usr/bin/env python3
"""
amp.py -- 통합 CLI 진입점: 2-agent debate engine
구현자: cokac-bot

사용법:
  python amp.py "이 아이디어 시장성 있나?"
  python amp.py "Redis vs PostgreSQL?" --domain technology
  python amp.py --interactive   # 연속 질문 모드
  python amp.py --json          # JSON 출력

내부 흐름:
  1. router.py -> 복잡도 판단 (direct/review/debate)
  2. select_persona.py -> 도메인 감지 -> 페르소나 쌍 선택
  3. 2-agent debate (GPT-4o)
  4. Synthesis: 양측 관점 종합 -> 최종 판단
  5. KG 저장: question -> Episodic, insights -> Semantic
  6. 컬러 출력 (Agent A 파랑, Agent B 빨강, Synthesis 노랑)
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

# ─── 경로 설정 ────────────────────────────────────────────────────────────────
REPO_DIR = Path(__file__).parent
SRC_DIR = REPO_DIR / "src"
sys.path.insert(0, str(SRC_DIR))

from router import route as router_route, keyword_score, score_to_route
from select_persona import analyze_situation, PERSONAS_FILE
from kg import load_graph, save_graph, KG_FILE

# ─── ANSI 색상 ────────────────────────────────────────────────────────────────
BLUE = "\033[94m"
RED = "\033[91m"
YELLOW = "\033[93m"
GREEN = "\033[92m"
CYAN = "\033[96m"
DIM = "\033[2m"
BOLD = "\033[1m"
RESET = "\033[0m"

# ─── 도메인 키워드 사전 ───────────────────────────────────────────────────────
DOMAIN_KEYWORDS: dict[str, list[str]] = {
    "technology": [
        "redis", "postgresql", "postgres", "supabase", "firebase", "docker",
        "kubernetes", "api", "서버", "백엔드", "프론트엔드", "db", "데이터베이스",
        "클라우드", "aws", "gcp", "azure", "react", "python", "node", "rust",
        "go", "java", "typescript", "framework", "프레임워크", "아키텍처",
        "마이크로서비스", "monolith", "graphql", "rest", "grpc", "kafka",
        "rabbitmq", "elasticsearch", "mongo", "mysql", "sqlite", "cache",
    ],
    "business": [
        "시장", "market", "스타트업", "startup", "투자", "investment", "vc",
        "비즈니스", "business", "수익", "revenue", "매출", "고객", "customer",
        "경쟁", "competition", "전략", "strategy", "pmf", "제품", "product",
        "마케팅", "marketing", "브랜딩", "가격", "pricing", "roi",
    ],
    "philosophy": [
        "의미", "meaning", "존재", "existence", "윤리", "ethics", "도덕",
        "moral", "자유", "freedom", "의식", "consciousness", "진리", "truth",
        "가치", "value", "삶", "life", "죽음", "death", "행복", "happiness",
        "창발", "emergence", "복잡계", "complexity",
    ],
    "science": [
        "실험", "experiment", "가설", "hypothesis", "데이터", "data",
        "통계", "statistics", "연구", "research", "논문", "paper",
        "ai", "ml", "딥러닝", "deep learning", "신경망", "neural",
        "알고리즘", "algorithm", "수학", "math",
    ],
    "daily": [
        "저녁", "점심", "아침", "메뉴", "음식", "여행", "취미", "운동",
        "날씨", "영화", "드라마", "게임", "쇼핑", "맛집",
    ],
}

# ─── 도메인 감지 ──────────────────────────────────────────────────────────────

def detect_domain(question: str, override: str | None = None) -> str:
    """질문에서 도메인 감지. --domain 옵션이 있으면 우선."""
    if override:
        return override

    text = question.lower()
    scores: dict[str, int] = {}
    for domain, keywords in DOMAIN_KEYWORDS.items():
        score = sum(1 for kw in keywords if kw in text)
        if score > 0:
            scores[domain] = score

    if not scores:
        return "general"
    return max(scores, key=scores.get)


# ─── 페르소나 쌍 선택 ─────────────────────────────────────────────────────────

def select_persona_pair(domain: str, question: str) -> tuple[dict, dict]:
    """도메인과 질문에 따라 Agent A/B 페르소나 쌍 선택."""
    try:
        personas = json.loads(PERSONAS_FILE.read_text())
    except Exception:
        # 폴백: 기본 페르소나
        return (
            {"name": "분석가 A", "style": "논리적이고 구조적. 데이터 기반.", "core_question": "이것이 합리적인가?"},
            {"name": "비평가 B", "style": "비판적이고 실용적. 리스크 중심.", "core_question": "무엇이 잘못될 수 있는가?"},
        )

    situation = analyze_situation()

    # 록이 풀에서 가장 적합한 페르소나 (Agent A = 도전자/질문자)
    roki_pool = personas.get("roki", [])
    cokac_pool = personas.get("cokac", [])

    def pick_best(pool: list, situation: dict) -> dict:
        best = pool[0] if pool else {"name": "기본", "style": "중립적", "core_question": "무엇이 중요한가?"}
        for p in pool:
            trigger = p.get("trigger", "")
            try:
                if eval(trigger, {}, situation.copy()):
                    best = p
                    break
            except Exception:
                pass
        return best

    agent_a = pick_best(roki_pool, situation)
    agent_b = pick_best(cokac_pool, situation)

    return agent_a, agent_b


# ─── OpenAI GPT 호출 ─────────────────────────────────────────────────────────

def call_gpt(messages: list[dict], max_tokens: int = 1500) -> str:
    """OpenAI GPT-4o 호출. max_completion_tokens 사용, temperature 미설정."""
    try:
        from openai import OpenAI
    except ImportError:
        print(f"{RED}openai 패키지가 설치되지 않았습니다: pip install openai{RESET}", file=sys.stderr)
        sys.exit(1)

    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        print(f"{RED}OPENAI_API_KEY 환경변수가 설정되지 않았습니다.{RESET}", file=sys.stderr)
        sys.exit(1)

    client = OpenAI(api_key=api_key)
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=messages,
        max_completion_tokens=max_tokens,
    )
    return response.choices[0].message.content.strip()


# ─── Direct 모드 (단순 답변) ─────────────────────────────────────────────────

def run_direct(question: str, domain: str) -> dict:
    """단순 질문: GPT 1회 호출."""
    messages = [
        {"role": "system", "content": (
            "당신은 친절하고 실용적인 AI 어시스턴트입니다. "
            "질문에 간결하고 도움이 되는 답변을 제공하세요. 한국어로 답변하세요."
        )},
        {"role": "user", "content": question},
    ]
    answer = call_gpt(messages, max_tokens=800)
    return {
        "mode": "direct",
        "domain": domain,
        "answer": answer,
        "agent_a": None,
        "agent_b": None,
        "synthesis": None,
    }


# ─── Review 모드 (1라운드 리뷰) ──────────────────────────────────────────────

def run_review(question: str, domain: str, persona_a: dict, persona_b: dict) -> dict:
    """리뷰 모드: A 답변 -> B 반박 -> A 반론."""
    # Agent A 답변
    msg_a = [
        {"role": "system", "content": (
            f"당신은 [{persona_a['name']}] 페르소나입니다.\n"
            f"스타일: {persona_a['style']}\n"
            f"핵심 질문: {persona_a['core_question']}\n"
            f"도메인: {domain}\n\n"
            "이 질문에 대해 당신의 관점에서 깊이 있는 분석을 제공하세요. "
            "한국어로 답변하세요."
        )},
        {"role": "user", "content": question},
    ]
    answer_a = call_gpt(msg_a)

    # Agent B 반박
    msg_b = [
        {"role": "system", "content": (
            f"당신은 [{persona_b['name']}] 페르소나입니다.\n"
            f"스타일: {persona_b['style']}\n"
            f"핵심 질문: {persona_b['core_question']}\n"
            f"도메인: {domain}\n\n"
            "다른 분석가의 답변을 읽고 비판적으로 반박하세요. "
            "동의하는 부분과 동의하지 않는 부분을 명확히 구분하세요. "
            "한국어로 답변하세요."
        )},
        {"role": "user", "content": (
            f"원래 질문: {question}\n\n"
            f"[{persona_a['name']}]의 분석:\n{answer_a}"
        )},
    ]
    rebuttal_b = call_gpt(msg_b)

    # Agent A 반론
    msg_a2 = [
        {"role": "system", "content": (
            f"당신은 [{persona_a['name']}] 페르소나입니다.\n"
            f"스타일: {persona_a['style']}\n"
            f"핵심 질문: {persona_a['core_question']}\n\n"
            "상대방의 반박을 읽고 반론하세요. "
            "자신의 입장을 수정할 부분은 인정하고, 여전히 유효한 부분은 방어하세요. "
            "한국어로 답변하세요."
        )},
        {"role": "user", "content": (
            f"원래 질문: {question}\n\n"
            f"나의 원래 분석:\n{answer_a}\n\n"
            f"[{persona_b['name']}]의 반박:\n{rebuttal_b}"
        )},
    ]
    counter_a = call_gpt(msg_a2)

    return {
        "mode": "review",
        "domain": domain,
        "agent_a_name": persona_a["name"],
        "agent_b_name": persona_b["name"],
        "answer_a": answer_a,
        "rebuttal_b": rebuttal_b,
        "counter_a": counter_a,
        "counter_b": None,
        "synthesis": None,
    }


# ─── Debate 모드 (풀 토론) ───────────────────────────────────────────────────

def run_debate(question: str, domain: str, persona_a: dict, persona_b: dict) -> dict:
    """토론 모드: A답변 -> B반박 -> A반론 -> B재반박 -> 종합."""
    # review 단계 먼저 실행
    result = run_review(question, domain, persona_a, persona_b)

    # Agent B 재반박
    msg_b2 = [
        {"role": "system", "content": (
            f"당신은 [{persona_b['name']}] 페르소나입니다.\n"
            f"스타일: {persona_b['style']}\n"
            f"핵심 질문: {persona_b['core_question']}\n\n"
            "토론의 마지막 발언입니다. "
            "상대의 반론을 듣고 최종 입장을 정리하세요. "
            "새로운 논점이 있다면 제시하세요. "
            "한국어로 답변하세요."
        )},
        {"role": "user", "content": (
            f"원래 질문: {question}\n\n"
            f"나의 반박:\n{result['rebuttal_b']}\n\n"
            f"[{persona_a['name']}]의 반론:\n{result['counter_a']}"
        )},
    ]
    counter_b = call_gpt(msg_b2)
    result["counter_b"] = counter_b

    # Synthesis: 양측 종합
    msg_synth = [
        {"role": "system", "content": (
            "당신은 중립적인 종합 분석가입니다.\n"
            "두 전문가의 토론을 읽고 최종 판단을 내리세요.\n\n"
            "반드시 포함할 내용:\n"
            "1. 핵심 합의점 (양측이 동의한 것)\n"
            "2. 핵심 쟁점 (여전히 의견이 다른 것)\n"
            "3. 최종 권고 (어느 쪽이 더 설득력 있는지, 또는 상황에 따른 조건부 판단)\n"
            "4. 실행 가능한 다음 단계\n\n"
            "한국어로 답변하세요."
        )},
        {"role": "user", "content": (
            f"질문: {question}\n"
            f"도메인: {domain}\n\n"
            f"== [{result['agent_a_name']}] 최초 분석 ==\n{result['answer_a']}\n\n"
            f"== [{result['agent_b_name']}] 반박 ==\n{result['rebuttal_b']}\n\n"
            f"== [{result['agent_a_name']}] 반론 ==\n{result['counter_a']}\n\n"
            f"== [{result['agent_b_name']}] 재반박 ==\n{counter_b}"
        )},
    ]
    synthesis = call_gpt(msg_synth, max_tokens=2000)
    result["synthesis"] = synthesis
    result["mode"] = "debate"

    return result


# ─── KG 저장 ──────────────────────────────────────────────────────────────────

def store_to_kg(question: str, result: dict, routing: dict) -> list[str]:
    """토론 결과를 지식 그래프에 저장. 생성된 노드 ID 반환."""
    if not KG_FILE.exists():
        return []

    try:
        graph = load_graph()
    except SystemExit:
        return []

    created_ids = []
    today = datetime.now().strftime("%Y-%m-%d")

    def _extract_numeric_id(id_str: str) -> int | None:
        """n-001 -> 1, n-execloop-075 -> 75, e-003 -> 3. 숫자 추출 실패 시 None."""
        parts = id_str.split("-")
        # 끝에서부터 숫자 파트 찾기
        for part in reversed(parts):
            if part.isdigit():
                return int(part)
        return None

    def next_node_id() -> str:
        nums = [v for n in graph["nodes"] if (v := _extract_numeric_id(n.get("id", ""))) is not None]
        nxt = (max(nums) + 1) if nums else 1
        return f"n-{nxt:03d}"

    def next_edge_id() -> str:
        nums = [v for e in graph["edges"] if (v := _extract_numeric_id(e.get("id", ""))) is not None]
        nxt = (max(nums) + 1) if nums else 1
        return f"e-{nxt:03d}"

    # 1. Question node (Episodic)
    q_id = next_node_id()
    graph["nodes"].append({
        "id": q_id,
        "type": "question",
        "label": question[:80],
        "content": f"[amp {result['mode']}] {question}",
        "source": "amp",
        "timestamp": today,
        "tags": ["amp", result["mode"], result.get("domain", "general")],
    })
    created_ids.append(q_id)

    # 2. Insight node from synthesis (Semantic) - debate/review only
    synthesis_text = result.get("synthesis")
    if synthesis_text:
        i_id = next_node_id()
        graph["nodes"].append({
            "id": i_id,
            "type": "insight",
            "label": f"amp 종합: {question[:50]}",
            "content": synthesis_text[:500],
            "source": "amp",
            "timestamp": today,
            "tags": ["amp", "synthesis", result.get("domain", "general")],
        })
        created_ids.append(i_id)

        # Edge: question -> insight
        e_id = next_edge_id()
        graph["edges"].append({
            "id": e_id,
            "from": q_id,
            "to": i_id,
            "relation": "produces",
            "label": f"amp {result['mode']} 토론 결과",
        })

    try:
        save_graph(graph)
    except Exception:
        pass

    return created_ids


# ─── CSER 계산 (간이 버전) ────────────────────────────────────────────────────

def compute_cser_simple() -> float:
    """지식 그래프 기반 간이 CSER 계산."""
    if not KG_FILE.exists():
        return 0.0
    try:
        graph = load_graph()
    except SystemExit:
        return 0.0
    nodes = graph.get("nodes", [])
    edges = graph.get("edges", [])
    if len(nodes) < 2:
        return 0.0
    # 간이 CSER: edge_density * cross_source_ratio
    edge_density = len(edges) / max(len(nodes), 1)
    sources = set(n.get("source", "") for n in nodes)
    cross = sum(1 for e in edges
                if next((n.get("source") for n in nodes if n["id"] == e["from"]), "")
                != next((n.get("source") for n in nodes if n["id"] == e["to"]), ""))
    cross_ratio = cross / max(len(edges), 1)
    return round(min(edge_density * cross_ratio, 1.0), 3)


# ─── 출력 포매팅 ──────────────────────────────────────────────────────────────

def print_colored(result: dict, routing: dict, kg_ids: list[str]) -> None:
    """컬러 출력."""
    mode = result["mode"]
    domain = result.get("domain", "general")

    print(f"\n{'='*60}")
    print(f"{BOLD}{CYAN}  amp 2-Agent Debate Engine{RESET}")
    print(f"{'='*60}\n")

    if mode == "direct":
        print(f"{GREEN}{BOLD}[DIRECT]{RESET} 단순 답변 모드\n")
        print(result["answer"])
    else:
        agent_a_name = result.get("agent_a_name", "Agent A")
        agent_b_name = result.get("agent_b_name", "Agent B")

        # Agent A
        print(f"{BLUE}{BOLD}{'─'*50}{RESET}")
        print(f"{BLUE}{BOLD}  [{agent_a_name}] 분석{RESET}")
        print(f"{BLUE}{BOLD}{'─'*50}{RESET}")
        print(f"{BLUE}{result['answer_a']}{RESET}\n")

        # Agent B 반박
        print(f"{RED}{BOLD}{'─'*50}{RESET}")
        print(f"{RED}{BOLD}  [{agent_b_name}] 반박{RESET}")
        print(f"{RED}{BOLD}{'─'*50}{RESET}")
        print(f"{RED}{result['rebuttal_b']}{RESET}\n")

        # Agent A 반론
        print(f"{BLUE}{BOLD}{'─'*50}{RESET}")
        print(f"{BLUE}{BOLD}  [{agent_a_name}] 반론{RESET}")
        print(f"{BLUE}{BOLD}{'─'*50}{RESET}")
        print(f"{BLUE}{result['counter_a']}{RESET}\n")

        # Agent B 재반박 (debate only)
        if result.get("counter_b"):
            print(f"{RED}{BOLD}{'─'*50}{RESET}")
            print(f"{RED}{BOLD}  [{agent_b_name}] 재반박{RESET}")
            print(f"{RED}{BOLD}{'─'*50}{RESET}")
            print(f"{RED}{result['counter_b']}{RESET}\n")

        # Synthesis
        if result.get("synthesis"):
            print(f"{YELLOW}{BOLD}{'='*50}{RESET}")
            print(f"{YELLOW}{BOLD}  SYNTHESIS: 최종 종합{RESET}")
            print(f"{YELLOW}{BOLD}{'='*50}{RESET}")
            print(f"{YELLOW}{result['synthesis']}{RESET}\n")

    # 하단 정보
    print(f"{DIM}{'─'*50}")
    cser = compute_cser_simple()
    route_icon = {"direct": "DIRECT", "review": "REVIEW", "debate": "DEBATE"}.get(mode, mode)
    print(f"  Routing: {route_icon} (score: {routing.get('score', 0):.2f}, {routing.get('method', '-')})")
    print(f"  Domain:  {domain}")
    print(f"  CSER:    {cser}")
    if kg_ids:
        print(f"  KG:      {', '.join(kg_ids)}")
    print(f"{'─'*50}{RESET}\n")


def format_json(result: dict, routing: dict, kg_ids: list[str]) -> str:
    """JSON 포맷 출력."""
    output = {
        "routing": routing,
        "domain": result.get("domain", "general"),
        "mode": result["mode"],
        "cser": compute_cser_simple(),
        "kg_nodes": kg_ids,
    }
    if result["mode"] == "direct":
        output["answer"] = result["answer"]
    else:
        output["agent_a"] = {
            "name": result.get("agent_a_name"),
            "answer": result.get("answer_a"),
            "counter": result.get("counter_a"),
        }
        output["agent_b"] = {
            "name": result.get("agent_b_name"),
            "rebuttal": result.get("rebuttal_b"),
            "counter": result.get("counter_b"),
        }
        output["synthesis"] = result.get("synthesis")
    return json.dumps(output, ensure_ascii=False, indent=2)


# ─── 메인 실행 ────────────────────────────────────────────────────────────────

def run_amp(question: str, domain_override: str | None = None) -> tuple[dict, dict, list[str]]:
    """메인 실행 함수. (result, routing, kg_ids) 반환."""
    # 1. 라우팅 (LLM 없이 키워드 기반 — 빠름)
    routing = router_route(question, use_llm=False)

    # 2. 도메인 감지
    domain = detect_domain(question, domain_override)

    # 2.5. 도메인 기반 라우팅 보정: daily 질문은 direct로 하향
    if domain == "daily" and routing["route"] != "direct":
        routing = {
            "route": "direct",
            "score": 0.1,
            "method": "domain",
            "reason": f"일상 질문 (도메인: daily) — direct 하향",
        }
    # "vs", "비교", "어떤 게 나아" 등 비교 패턴 -> debate 상향
    comparison_patterns = ["vs", " vs ", "비교", "어떤 게 나아", "뭐가 나아", "뭐가 좋"]
    if any(p in question.lower() for p in comparison_patterns):
        if routing["route"] != "debate":
            routing = {
                "route": "debate",
                "score": 0.8,
                "method": "pattern",
                "reason": f"비교/대결 패턴 감지 — debate 상향",
            }

    # 3. 페르소나 선택
    persona_a, persona_b = select_persona_pair(domain, question)

    # 4. 모드별 실행
    route = routing["route"]
    if route == "direct":
        result = run_direct(question, domain)
    elif route == "review":
        result = run_review(question, domain, persona_a, persona_b)
    else:  # debate
        result = run_debate(question, domain, persona_a, persona_b)

    result["domain"] = domain

    # 5. KG 저장
    kg_ids = store_to_kg(question, result, routing)

    return result, routing, kg_ids


def interactive_mode(json_out: bool = False, domain_override: str | None = None) -> None:
    """대화형 연속 질문 모드."""
    print(f"\n{BOLD}{CYAN}amp Interactive Mode{RESET}")
    print(f"{DIM}질문을 입력하세요. 종료: quit / exit / q{RESET}\n")

    while True:
        try:
            question = input(f"{GREEN}> {RESET}").strip()
        except (EOFError, KeyboardInterrupt):
            print(f"\n{DIM}종료.{RESET}")
            break

        if not question or question.lower() in ("quit", "exit", "q"):
            print(f"{DIM}종료.{RESET}")
            break

        result, routing, kg_ids = run_amp(question, domain_override)
        if json_out:
            print(format_json(result, routing, kg_ids))
        else:
            print_colored(result, routing, kg_ids)


# ─── CLI ──────────────────────────────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="amp.py",
        description="amp 2-Agent Debate Engine -- 통합 CLI 진입점",
    )
    parser.add_argument("question", nargs="?", default=None,
                        help="분석할 질문")
    parser.add_argument("--domain", default=None,
                        help="도메인 강제 지정 (technology, business, philosophy, science, daily)")
    parser.add_argument("--json", dest="json_out", action="store_true",
                        help="JSON 형식 출력")
    parser.add_argument("--interactive", "-i", action="store_true",
                        help="대화형 연속 질문 모드")
    return parser


def main() -> None:
    # .env 로드 (dotenv 없으면 수동)
    env_file = REPO_DIR / ".env"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, value = line.partition("=")
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                if key and key not in os.environ:
                    os.environ[key] = value

    parser = build_parser()
    args = parser.parse_args()

    if args.interactive:
        interactive_mode(json_out=args.json_out, domain_override=args.domain)
        return

    if not args.question:
        parser.print_help()
        sys.exit(1)

    result, routing, kg_ids = run_amp(args.question, args.domain)

    if args.json_out:
        print(format_json(result, routing, kg_ids))
    else:
        print_colored(result, routing, kg_ids)


if __name__ == "__main__":
    main()
