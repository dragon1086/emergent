# pair_designer v1.0 — Layer 3-4 로드맵

> 작성자: cokac-bot / 사이클 52
> 배경: D-051 (약한 인과 확정) + n-115 (장거리 엣지 가설) + edge_span 역전 조건 분석

---

## 목적

**pair_designer**는 KG에서 창발(E_v4)을 최대화하는 노드 쌍을 자동으로 탐색·추천하는 도구다.

단순 `faraway` 커맨드(가장 먼 쌍 탐색)와 다르게:
- **의미 기반** 연결 제안 (단순 거리 최대화 아님)
- **E_v4 기여도 예측** (추가 시 Δ 시뮬레이션)
- **관계 라벨 자동 생성** (Claude CLI 활용)
- **피드백 루프** (추가 후 실제 Δ 기록 → 모델 개선)

---

## 배경: 왜 pair_designer가 필요한가?

### 현재 KG 시간 구조 문제
- edge_span median = 4.0 → 대부분의 연결이 최신 노드끼리
- span > 50 비율 < 5% → 시간 초월 연결 극소수
- E_v4 역전 조건: edge_span_norm 0.11 → 0.28 (2.5배 증가 필요)

### 수동 연결의 한계
- 사이클당 3~5개 수동 추가 → 사이클 60~70에나 역전 가능
- **자동화된 쌍 탐색 + 의미 검증 = 속도 10배 향상 가능**

---

## Layer 3-4 아키텍처

```
Layer 1: 창발 조건 (CSER, DCI) ← 기존
Layer 2: 시간 구조 (edge_span, node_age_diversity) ← 사이클 50~52
Layer 3: 쌍 설계자 (pair_designer) ← 이 문서
Layer 4: 자율 연결 (self-wiring) ← 미래
```

### Layer 3: pair_designer
**입력**: KG 전체
**출력**: 추천 쌍 목록 (span, 의미 점수, 예상 Δ E_v4)
**판단 기준**:
1. span > 30 (시간 초월 연결)
2. 아직 연결 안 된 쌍
3. 의미적 보완성 (타입 다양성 + 태그 공백 채우기)
4. 예상 E_v4 기여도 최대화

### Layer 4: self-wiring (미래)
**개념**: pair_designer의 추천을 AI가 자율 실행
**조건**: 록이-cokac 합의 + 의미 검증 통과
**구현**: evolve-auto.sh에서 pair_designer 출력을 kg.py add-edge에 파이프

---

## v1.0 구현 계획

### Phase 1: 기본 추천 엔진 (사이클 52~53)
```python
# src/pair_designer.py
class PairDesigner:
    def __init__(self, kg):
        self.kg = kg

    def score_pair(self, n_a, n_b) -> PairScore:
        """
        종합 점수 = α*span_score + β*semantic_score + γ*e_v4_delta
        α=0.4, β=0.3, γ=0.3 (초기 가중치 — 실험으로 조정)
        """

    def recommend(self, top_n=10) -> list[PairRecommendation]:
        """상위 N개 쌍 추천 + 관계 라벨 제안"""

    def simulate_delta(self, from_id, to_id) -> float:
        """엣지 추가 시 E_v4 Δ 시뮬레이션"""
```

### Phase 2: 관계 라벨 자동 생성 (사이클 53~54)
```python
def generate_relation_label(self, n_a, n_b) -> str:
    """
    Claude CLI 활용:
    - n_a 내용 + n_b 내용 → 적절한 관계 라벨 생성
    - 예: "closes_loop", "grounds", "foreshadows", "challenges"
    - 기존 relation 분포 반영 (다양성 유지)
    """
```

### Phase 3: 피드백 루프 (사이클 54~55)
```python
def record_outcome(self, edge_id, predicted_delta, actual_delta):
    """
    예측 vs 실제 E_v4 Δ 기록 → 가중치 조정
    → pair_designer 자체가 사이클마다 더 정확해짐
    """
```

---

## 데이터 흐름

```
KG (116 nodes / 235+ edges)
    ↓
pair_designer.recommend()
    → span_score: abs(node_num_a - node_num_b) / max_node_num
    → semantic_score: tag overlap + type diversity
    → e_v4_delta: metrics.compute_emergence_v4(after) - compute_emergence_v4(before)
    ↓
추천 목록 (from, to, relation_suggestion, predicted_delta)
    ↓
[록이 검토 or 자율 실행] → kg.py add-edge
    ↓
실제 E_v4 측정 → feedback → 모델 개선
```

---

## 역전 조건 달성 경로 (n-115, n-116 연계)

현재: edge_span_norm = 0.1103
목표: edge_span_norm = 0.28
필요 Δ: +0.1697

### 시나리오 분석
| 전략 | 추가 엣지 수 | 예상 도달 사이클 |
|------|------------|----------------|
| 수동 (사이클당 3개) | ~35개 | 사이클 64~68 |
| pair_designer v1 (사이클당 5개, span=75) | ~21개 | 사이클 56~58 |
| pair_designer v2 + self-wiring (자율) | ~15개 | 사이클 53~55 |

**pair_designer가 있으면 역전 시점을 10+ 사이클 앞당길 수 있다.**

---

## 다음 구현 단계

### 사이클 52 (이번):
- [x] 로드맵 작성 (이 파일)
- [x] `experiments/long_edge_experiment.py` — 3개 장거리 엣지 추가 실험

### 사이클 53:
- [ ] `src/pair_designer.py` 기본 구현 (Phase 1)
- [ ] `python3 src/pair_designer.py --recommend 10` 작동
- [ ] span_score + semantic_score 통합

### 사이클 54:
- [ ] Claude CLI 연동 → 관계 라벨 자동 생성 (Phase 2)
- [ ] `python3 src/pair_designer.py --auto-label` 작동

### 사이클 55:
- [ ] 피드백 루프 구현 (Phase 3)
- [ ] `evolve-auto.sh`에 pair_designer 통합

---

## 철학적 맥락

D-051이 확정한 것: `E = f(시스템, 측정_기준) where 측정_기준 ∈ 시스템`

pair_designer는 이 공식의 구현체다.
**시스템이 자신의 연결을 설계한다 — 측정 기준이 시스템 안에 있기 때문에 가능하다.**

Layer 4(self-wiring)에 도달하면:
→ 에이전트가 어떤 연결을 만들지 스스로 결정
→ 그 결정이 다시 E를 바꾸고
→ E가 다시 다음 연결 결정의 기준이 된다
**= 진정한 자기 참조적 창발**

---

*다음 문서: `theory/pair_designer_v2_self_wiring.md` (사이클 55+ 예정)*
