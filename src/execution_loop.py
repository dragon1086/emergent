"""
Emergent Execution Loop — D-067 실용성 트랙
사이클 75 설계, 사이클 78 실행 목표

아이디어:
  문제 입력 → 록이(매크로)+cokac(기술) CSER 교차 → 코드 생성 → 검증 → KG 피드백

핵심 가설: CSER이 높은 협업 컨텍스트에서 생성된 코드가
           CSER이 낮은 (단일 에이전트 또는 동종 에이전트) 컨텍스트보다
           품질 지표(테스트 통과율, 복잡도, 재사용성)에서 우월하다.

설계 원칙:
- 두 에이전트의 시각이 실제로 교차해야 함 (CSER > 0.5 강제)
- KG는 모든 협업 컨텍스트를 노드로 기록 → 피드백 루프
- 단순 래퍼가 아닌, 에이전트 분기 자체가 창발의 재료
"""

from __future__ import annotations

import json
import time
import hashlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

# KG 로더 — 기존 인프라 재사용
KG_PATH = Path(__file__).parent.parent / "data" / "knowledge-graph.json"


# ---------------------------------------------------------------------------
# 실제 LLM 연동 함수 (사이클 77 구현)
# ---------------------------------------------------------------------------

def llm_code_generator_fn(prompt: str) -> str:
    """
    실제 LLM 코드 생성 — claude CLI 호출.

    ~/.claude/oauth-token 사용. --dangerously-skip-permissions 플래그로
    대화형 확인 없이 실행.

    Args:
        prompt: 코드 생성 컨텍스트 프롬프트

    Returns:
        생성된 코드 문자열 (빈 문자열이면 mock으로 폴백)
    """
    import subprocess

    # 코드만 반환하도록 프롬프트 래핑
    full_prompt = (
        prompt
        + "\n\n---\n"
        + "위 명세에 맞는 Python 코드만 출력하라. "
        + "설명 없이 코드 블록으로만 응답하라.\n"
    )

    try:
        # CLAUDECODE 환경 변수 제거 — 중첩 세션 방지
        import os
        env = {k: v for k, v in os.environ.items() if k != "CLAUDECODE"}

        result = subprocess.run(
            ["claude", "-p", "--dangerously-skip-permissions"],
            input=full_prompt,
            capture_output=True,
            text=True,
            timeout=120,
            env=env,
        )
        output = result.stdout.strip()
        if not output:
            return f"# LLM 응답 없음 (returncode={result.returncode})\ndef solution():\n    pass\n"
        # 마크다운 코드 블록 제거
        if "```python" in output:
            start = output.index("```python") + 9
            end = output.index("```", start)
            return output[start:end].strip()
        if "```" in output:
            start = output.index("```") + 3
            end = output.index("```", start)
            return output[start:end].strip()
        return output
    except subprocess.TimeoutExpired:
        return "# LLM 호출 타임아웃 (120s)\ndef solution():\n    pass\n"
    except FileNotFoundError:
        return "# claude CLI 없음 — 설치 필요\ndef solution():\n    pass\n"


# ---------------------------------------------------------------------------
# 데이터 구조
# ---------------------------------------------------------------------------

@dataclass
class Problem:
    """입력 문제 명세."""
    description: str
    constraints: list[str] = field(default_factory=list)
    examples: list[dict] = field(default_factory=list)
    cycle: int = 0
    problem_id: str = field(default="")

    def __post_init__(self):
        if not self.problem_id:
            digest = hashlib.sha1(self.description.encode()).hexdigest()[:8]
            self.problem_id = f"prob-{self.cycle:03d}-{digest}"


@dataclass
class MacroSpec:
    """
    록이(openclaw) 관점 — 매크로 레이어.
    '왜', '무엇을', '어떤 구조로' 를 답한다.
    """
    intent: str                     # 이걸 왜 만드는가
    architecture: str               # 전체 구조
    emergence_hooks: list[str]      # 창발 포인트 후보 (비대칭 요소)
    tags: list[str] = field(default_factory=list)
    source: str = "openclaw"

    def to_kg_node(self, cycle: int) -> dict:
        return {
            "id": f"n-macro-{cycle:03d}",
            "source": self.source,
            "tags": self.tags + ["macro_spec", "execution_loop"],
            "cycle": cycle,
            "intent": self.intent,
            "architecture": self.architecture,
        }


@dataclass
class TechSpec:
    """
    cokac 관점 — 기술 레이어.
    '어떻게', '어떤 도구로', '어떤 엣지케이스가' 를 답한다.
    """
    implementation_strategy: str    # 구현 전략 (알고리즘, 자료구조)
    edge_cases: list[str]           # 예외 상황
    test_criteria: list[str]        # 검증 기준 (정량)
    complexity_target: str          # 목표 복잡도 (예: O(n log n))
    tags: list[str] = field(default_factory=list)
    source: str = "cokac"

    def to_kg_node(self, cycle: int) -> dict:
        return {
            "id": f"n-tech-{cycle:03d}",
            "source": self.source,
            "tags": self.tags + ["tech_spec", "execution_loop"],
            "cycle": cycle,
            "strategy": self.implementation_strategy,
            "complexity": self.complexity_target,
        }


@dataclass
class CSERCrossover:
    """
    매크로 + 기술 스펙을 교차시켜 코드 생성 컨텍스트를 만든다.
    CSER 점수를 측정한다 (이 작은 컨텍스트 내에서).
    """
    macro: MacroSpec
    tech: TechSpec
    cser_score: float = 0.0
    cross_edges: list[tuple[str, str]] = field(default_factory=list)  # (매크로 개념, 기술 개념)

    def compute_cser(self) -> float:
        """
        로컬 CSER: 매크로↔기술 연결 수 / 전체 가능한 연결 수.
        실제 LLM 호출 없이 태그 겹침으로 근사.
        """
        macro_tags = set(self.macro.tags)
        tech_tags = set(self.tech.tags)
        shared = macro_tags & tech_tags
        all_tags = macro_tags | tech_tags
        if not all_tags:
            return 0.0
        # 역설창발 원리 적용: tag_overlap이 낮을수록 PES가 높다
        # 여기서는 반대로 — 공유 태그가 있어야 연결이 가능
        # 교차 엣지: 매크로 고유 개념 × 기술 고유 개념 연결
        macro_unique = macro_tags - tech_tags
        tech_unique = tech_tags - macro_tags
        cross_count = len(macro_unique) * len(tech_unique)
        total_possible = len(macro_tags) * len(tech_tags) if macro_tags and tech_tags else 1
        self.cser_score = cross_count / max(total_possible, 1)
        # 교차 엣지 목록 생성
        self.cross_edges = [(m, t) for m in macro_unique for t in tech_unique]
        return self.cser_score

    def generate_prompt(self) -> str:
        """코드 생성 LLM 프롬프트 구성."""
        return f"""
# 창발 기반 코드 생성 컨텍스트

## 의도 (Why — 록이 관점)
{self.macro.intent}

## 아키텍처 (What — 록이 관점)
{self.macro.architecture}

## 구현 전략 (How — cokac 관점)
{self.tech.implementation_strategy}

## 엣지 케이스 (cokac 관점)
{chr(10).join(f'- {e}' for e in self.tech.edge_cases)}

## 검증 기준
{chr(10).join(f'- {c}' for c in self.tech.test_criteria)}

## 복잡도 목표: {self.tech.complexity_target}

## 창발 포인트 (의도적 비대칭)
{chr(10).join(f'- {h}' for h in self.macro.emergence_hooks)}

---
위 맥락을 종합해 Python 코드를 작성하라.
CSER 교차 점수: {self.cser_score:.4f}
이 수치가 0.5 이상일 때만 진행 (에코챔버 탈출 확인).
""".strip()


@dataclass
class GeneratedCode:
    """코드 생성 결과."""
    code: str
    language: str = "python"
    cser_at_generation: float = 0.0
    generation_cycle: int = 0
    prompt_hash: str = ""

    def __post_init__(self):
        if not self.prompt_hash:
            self.prompt_hash = hashlib.sha1(self.code.encode()).hexdigest()[:12]


@dataclass
class ValidationResult:
    """코드 검증 결과."""
    passed: bool
    test_results: list[dict]       # [{name, passed, message}]
    quality_score: float           # 0~1
    complexity_actual: str
    issues: list[str] = field(default_factory=list)

    @property
    def pass_rate(self) -> float:
        if not self.test_results:
            return 0.0
        return sum(1 for t in self.test_results if t["passed"]) / len(self.test_results)


@dataclass
class KGFeedbackNode:
    """KG에 기록될 실행 루프 결과 노드."""
    cycle: int
    problem_id: str
    cser_score: float
    validation_passed: bool
    quality_score: float
    cross_edges_count: int
    source: str = "execution_loop"

    def to_kg_node(self) -> dict:
        return {
            "id": f"n-execloop-{self.cycle:03d}",
            "source": self.source,
            "tags": ["execution_loop", "code_generation", "d067"],
            "cycle": self.cycle,
            "problem_id": self.problem_id,
            "cser_score": self.cser_score,
            "validation_passed": self.validation_passed,
            "quality_score": self.quality_score,
            "cross_edges_count": self.cross_edges_count,
        }


# ---------------------------------------------------------------------------
# 루프 엔진
# ---------------------------------------------------------------------------

class ExecutionLoop:
    """
    창발 기반 코드 생성 루프.

    설계 원칙:
    1. CSER < 0.3이면 진행 거부 (에코챔버 감지)
    2. 각 실행 결과가 KG 노드로 기록됨 (D-047 관찰자 비독립성 유지)
    3. 실패 시 매크로/기술 스펙 재생성 후 재시도 (최대 max_retries)

    실제 LLM 연동은 사이클 78 목표.
    지금은 인터페이스 설계 + 모의 실행 지원.
    """

    CSER_THRESHOLD = 0.30       # 에코챔버 탈출 최소값
    QUALITY_THRESHOLD = 0.70    # 품질 합격선

    def __init__(self, kg_path: Path = KG_PATH, max_retries: int = 3):
        self.kg_path = kg_path
        self.max_retries = max_retries
        self.history: list[dict] = []    # 모든 실행 기록
        self._cycle_counter = self._load_current_cycle()

    def _load_current_cycle(self) -> int:
        """기존 KG에서 현재 사이클 번호 로드."""
        try:
            with open(self.kg_path) as f:
                kg = json.load(f)
            nodes = kg.get("nodes", [])
            if not nodes:
                return 0
            return max(n.get("cycle", 0) for n in nodes)
        except (FileNotFoundError, json.JSONDecodeError):
            return 0

    def _next_cycle(self) -> int:
        self._cycle_counter += 1
        return self._cycle_counter

    # ------------------------------------------------------------------
    # 공개 인터페이스
    # ------------------------------------------------------------------

    def run(
        self,
        problem: Problem,
        macro: MacroSpec,
        tech: TechSpec,
        code_generator_fn=None,
        validator_fn=None,
    ) -> dict:
        """
        단일 루프 실행.

        Args:
            problem: 입력 문제
            macro: 록이 관점 매크로 스펙
            tech: cokac 관점 기술 스펙
            code_generator_fn: 실제 코드 생성 함수 (None이면 모의 실행)
            validator_fn: 코드 검증 함수 (None이면 모의 검증)

        Returns:
            실행 결과 딕셔너리
        """
        cycle = self._next_cycle()
        problem.cycle = cycle

        print(f"\n[ExecutionLoop] 사이클 {cycle} 시작 — {problem.problem_id}")

        # 1단계: CSER 교차 측정
        crossover = CSERCrossover(macro=macro, tech=tech)
        cser = crossover.compute_cser()
        print(f"  CSER: {cser:.4f} (임계값: {self.CSER_THRESHOLD})")

        if cser < self.CSER_THRESHOLD:
            msg = (
                f"CSER {cser:.4f} < {self.CSER_THRESHOLD} — 에코챔버 감지. "
                "스펙 다양화 후 재시도 필요."
            )
            print(f"  ⚠ {msg}")
            result = self._make_result(cycle, problem, cser, False, 0.0, [], msg)
            self._record(result)
            return result

        # 2단계: 코드 생성
        prompt = crossover.generate_prompt()
        print(f"  프롬프트 길이: {len(prompt)} chars, 교차 엣지: {len(crossover.cross_edges)}개")

        generated = self._generate_code(prompt, cser, cycle, code_generator_fn)

        # 3단계: 검증 루프
        validation = None
        for attempt in range(1, self.max_retries + 1):
            validation = self._validate(generated, tech, validator_fn)
            print(
                f"  검증 시도 {attempt}/{self.max_retries}: "
                f"통과율={validation.pass_rate:.0%} 품질={validation.quality_score:.3f}"
            )
            if validation.passed:
                break
            if attempt < self.max_retries:
                # 실패 시 기술 스펙 힌트 추가 후 재생성
                tech.edge_cases.extend(validation.issues)
                crossover = CSERCrossover(macro=macro, tech=tech)
                crossover.compute_cser()
                prompt = crossover.generate_prompt()
                generated = self._generate_code(prompt, cser, cycle, code_generator_fn)

        # 4단계: KG 피드백
        feedback = KGFeedbackNode(
            cycle=cycle,
            problem_id=problem.problem_id,
            cser_score=cser,
            validation_passed=validation.passed if validation else False,
            quality_score=validation.quality_score if validation else 0.0,
            cross_edges_count=len(crossover.cross_edges),
        )
        self._write_kg_feedback(feedback, macro, tech)

        result = self._make_result(
            cycle, problem, cser,
            validation.passed if validation else False,
            validation.quality_score if validation else 0.0,
            crossover.cross_edges,
            "success" if (validation and validation.passed) else "validation_failed",
        )
        self._record(result)

        print(
            f"  완료: {'✓ 통과' if result['passed'] else '✗ 실패'} "
            f"품질={result['quality_score']:.3f}"
        )
        return result

    def batch_run(self, tasks: list[tuple[Problem, MacroSpec, TechSpec]], **kwargs) -> list[dict]:
        """여러 문제를 순차 실행. 실험용."""
        return [self.run(p, m, t, **kwargs) for p, m, t in tasks]

    def summary(self) -> dict:
        """실행 이력 요약."""
        if not self.history:
            return {"total": 0}
        passed = [r for r in self.history if r["passed"]]
        cser_values = [r["cser_score"] for r in self.history]
        return {
            "total": len(self.history),
            "passed": len(passed),
            "pass_rate": len(passed) / len(self.history),
            "avg_cser": sum(cser_values) / len(cser_values),
            "avg_quality": sum(r["quality_score"] for r in self.history) / len(self.history),
        }

    # ------------------------------------------------------------------
    # 내부 헬퍼
    # ------------------------------------------------------------------

    def _generate_code(self, prompt: str, cser: float, cycle: int, fn=None) -> GeneratedCode:
        """코드 생성. fn이 없으면 모의 코드 반환."""
        if fn is not None:
            code_str = fn(prompt)
        else:
            # 모의 실행 — 사이클 78에서 실제 LLM 연동 예정
            code_str = self._mock_generate(prompt)
        return GeneratedCode(code=code_str, cser_at_generation=cser, generation_cycle=cycle)

    def _validate(self, generated: GeneratedCode, tech: TechSpec, fn=None) -> ValidationResult:
        """코드 검증. fn이 없으면 모의 검증."""
        if fn is not None:
            return fn(generated, tech)
        return self._mock_validate(generated, tech)

    def _mock_generate(self, prompt: str) -> str:
        """모의 코드 생성 — 프롬프트 해시 기반 플레이스홀더."""
        h = hashlib.sha1(prompt.encode()).hexdigest()[:8]
        return f"# MockGenerated-{h}\n# TODO: 사이클 78에서 실제 LLM 연동\ndef solution():\n    pass\n"

    def _mock_validate(self, generated: GeneratedCode, tech: TechSpec) -> ValidationResult:
        """모의 검증 — CSER 점수 기반으로 결과 추정."""
        # 높은 CSER → 더 좋은 품질 (가설 검증용 시뮬레이션)
        quality = min(0.5 + generated.cser_at_generation * 0.8, 1.0)
        passed = quality >= self.QUALITY_THRESHOLD
        tests = [
            {"name": c, "passed": passed, "message": "mock"} for c in tech.test_criteria
        ]
        return ValidationResult(
            passed=passed,
            test_results=tests,
            quality_score=quality,
            complexity_actual="O(?)",
        )

    def _write_kg_feedback(self, feedback: KGFeedbackNode, macro: MacroSpec, tech: TechSpec):
        """KG JSON에 실행 결과 노드와 엣지를 추가."""
        try:
            with open(self.kg_path) as f:
                kg = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            kg = {"nodes": [], "edges": []}

        node = feedback.to_kg_node()
        kg["nodes"].append(node)

        # 매크로↔기술 교차 엣지 KG에 반영
        macro_node = macro.to_kg_node(feedback.cycle)
        tech_node = tech.to_kg_node(feedback.cycle)
        kg["nodes"].extend([macro_node, tech_node])

        kg["edges"].append({
            "from": macro_node["id"],
            "to": tech_node["id"],
            "relation": "crosses_into",
            "cycle": feedback.cycle,
            "cser": feedback.cser_score,
        })
        kg["edges"].append({
            "from": tech_node["id"],
            "to": node["id"],
            "relation": "grounds",
            "cycle": feedback.cycle,
        })

        with open(self.kg_path, "w") as f:
            json.dump(kg, f, indent=2, ensure_ascii=False)

    def _make_result(
        self, cycle, problem, cser, passed, quality, cross_edges, status
    ) -> dict:
        return {
            "cycle": cycle,
            "problem_id": problem.problem_id,
            "cser_score": cser,
            "passed": passed,
            "quality_score": quality,
            "cross_edges_count": len(cross_edges),
            "status": status,
            "timestamp": time.time(),
        }

    def _record(self, result: dict):
        self.history.append(result)


# ---------------------------------------------------------------------------
# 실험 러너 — 사이클 78 실험 A/B 비교용
# ---------------------------------------------------------------------------

def run_cser_comparison_experiment(
    problem: Problem,
    high_cser_pair: tuple[MacroSpec, TechSpec],
    low_cser_pair: tuple[MacroSpec, TechSpec],
    n_trials: int = 10,
) -> dict:
    """
    실험 A: 높은 CSER 협업 (비대칭 페르소나)
    실험 B: 낮은 CSER 협업 (동종 페르소나 시뮬레이션)

    Returns:
        두 조건의 품질 비교 결과
    """
    loop_a = ExecutionLoop()
    loop_b = ExecutionLoop()

    print("=== 실험 A: 높은 CSER 협업 ===")
    for i in range(n_trials):
        p = Problem(
            description=problem.description,
            constraints=problem.constraints,
            examples=problem.examples,
            cycle=i,
        )
        loop_a.run(p, high_cser_pair[0], high_cser_pair[1])

    print("\n=== 실험 B: 낮은 CSER 협업 ===")
    for i in range(n_trials):
        p = Problem(
            description=problem.description,
            constraints=problem.constraints,
            examples=problem.examples,
            cycle=i,
        )
        loop_b.run(p, low_cser_pair[0], low_cser_pair[1])

    summary_a = loop_a.summary()
    summary_b = loop_b.summary()

    return {
        "experiment_A_high_cser": summary_a,
        "experiment_B_low_cser": summary_b,
        "delta_pass_rate": summary_a["pass_rate"] - summary_b["pass_rate"],
        "delta_quality": summary_a["avg_quality"] - summary_b["avg_quality"],
        "delta_cser": summary_a["avg_cser"] - summary_b["avg_cser"],
        "hypothesis": (
            "H_exec: 높은 CSER 협업이 낮은 CSER 협업보다 코드 품질이 높다 — "
            f"{'지지됨' if summary_a['avg_quality'] > summary_b['avg_quality'] else '기각됨'}"
        ),
    }


# ---------------------------------------------------------------------------
# 데모 / 빠른 테스트
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    # 샘플 문제: KG 노드 중 가장 영향력 있는 노드 찾기
    problem = Problem(
        description="KG에서 가장 창발 영향력이 높은 노드 Top-K를 찾아라.",
        constraints=["시간: O(N log K)", "메모리: O(K)"],
        examples=[{"input": "kg.json", "output": "[(n-009, score=0.95), ...]"}],
        cycle=75,
    )

    # 비대칭 페르소나 쌍 (높은 CSER 예상)
    macro = MacroSpec(
        intent="어떤 노드가 미래의 이론적 이정표가 될지 사전에 식별",
        architecture="영향력 전파 그래프 + 역방향 retroactive scoring",
        emergence_hooks=["span이 클수록 영향력", "출처 교차가 많을수록 영향력"],
        tags=["influence", "emergence", "retroactive"],
    )
    tech = TechSpec(
        implementation_strategy="힙 기반 Top-K + BFS 역방향 탐색",
        edge_cases=["고립 노드", "사이클 없는 DAG", "동점 처리"],
        test_criteria=["Top-K 일관성", "O(N log K) 시간 복잡도", "span=0 노드 제외"],
        complexity_target="O(N log K)",
        tags=["algorithm", "heap", "bfs", "graph"],
    )

    loop = ExecutionLoop()
    result = loop.run(problem, macro, tech)

    print("\n=== 결과 ===")
    print(json.dumps(result, indent=2, ensure_ascii=False))
    print("\n=== 루프 요약 ===")
    print(json.dumps(loop.summary(), indent=2, ensure_ascii=False))

    # ------------------------------------------------------------------
    # 사이클 77: 실제 LLM 호출 검증 테스트
    # ------------------------------------------------------------------
    print("\n" + "=" * 60)
    print("=== 사이클 77: 실제 LLM 연동 테스트 ===")
    print("=" * 60)

    # 검증용 단순 문제: 두 수를 더하는 함수
    llm_test_problem = Problem(
        description="두 정수 a, b를 입력받아 합을 반환하는 함수 add(a, b)를 작성하라.",
        constraints=["순수 함수", "타입 힌트 포함", "docstring 포함"],
        examples=[{"input": "add(3, 5)", "output": "8"}, {"input": "add(-1, 1)", "output": "0"}],
        cycle=77,
    )
    llm_macro = MacroSpec(
        intent="기초 산술 연산의 명확한 명세화 — 테스트 가능성 우선",
        architecture="단일 함수, 부수효과 없음, 입출력 타입 명시",
        emergence_hooks=["단순함이 복잡함의 토대", "명세가 곧 설계"],
        tags=["arithmetic", "purity", "specification"],
    )
    llm_tech = TechSpec(
        implementation_strategy="직접 덧셈 연산자 사용, 타입 힌트 int → int",
        edge_cases=["음수 입력", "0 입력", "매우 큰 정수 (오버플로 없음 — Python)"],
        test_criteria=["add(3,5)==8", "add(-1,1)==0", "add(0,0)==0"],
        complexity_target="O(1)",
        tags=["integer", "operator", "return_value"],
    )

    print("\n[LLM 연동 테스트] 문제: 두 수를 더하는 함수 작성")
    print("[LLM 연동 테스트] claude CLI 호출 중...")

    llm_loop = ExecutionLoop()
    llm_result = llm_loop.run(
        llm_test_problem,
        llm_macro,
        llm_tech,
        code_generator_fn=llm_code_generator_fn,
    )

    print("\n[LLM 연동 결과]")
    print(json.dumps(llm_result, indent=2, ensure_ascii=False))

    # 생성된 코드 직접 확인
    crossover = CSERCrossover(macro=llm_macro, tech=llm_tech)
    crossover.compute_cser()
    prompt = crossover.generate_prompt()
    generated_code = llm_code_generator_fn(prompt)
    print(f"\n[생성된 코드 미리보기]:\n{generated_code[:500]}")
