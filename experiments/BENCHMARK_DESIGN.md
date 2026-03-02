# TASK-003: amp Benchmark Design

## Overview

amp는 두 AI 에이전트가 서로 다른 페르소나로 토론하여 더 나은 답변을 생성하는 로컬 오픈소스 개인 어시스턴트다. 이 벤치마크는 **auto-persona 기능의 효과를 측정**한다.

- **Control (OFF)**: 하드코딩된 "Analyst" + "Critic" 페르소나
- **Treatment (ON)**: 질문 도메인에 맞게 자동 선택된 대립 페르소나

---

## 1. Methodology

### 1.1 실험 구조

```
질문 (10개)
    │
    ├─ [Control] Analyst vs Critic → 4-turn 토론 → answer_off
    │
    └─ [Treatment] Domain-A vs Domain-B → 4-turn 토론 → answer_on
                                                │
                                                ▼
                               블라인드 A/B 프레임워크
                               (Gemini 판사에게 레이블 비공개)
                                                │
                               ┌────────────────┴────────────────┐
                               │                                 │
                          Quality 점수                    Blind spot 측정
                          Completeness 점수               (GPT 추출 → 비교)
                          A/B winner 선택
```

### 1.2 4-Turn 토론 형식

| Turn | 역할 | 내용 |
|------|------|------|
| 1 | Agent A | 초기 입장 제시 |
| 2 | Agent B | 반박 및 대립 관점 |
| 3 | Agent A | 재반박 및 논거 강화 |
| 4 | 중립 통합자 | 종합 결론 및 권고사항 |

모든 조건에서 동일한 GPT-5.2 모델, 동일한 4-turn 형식 사용.

---

## 2. Why Gemini Judge (GPT-5.2 자기평가 편향)

### 문제: LLM 자기 선호 편향 (Self-Preference Bias)

GPT-5.2가 자신이 생성한 답변을 평가하면 **자신이 선호하는 스타일과 구조를 더 높게 평가하는 경향**이 있다. 이는:

- 두 조건 모두 GPT-5.2가 생성했으므로 평가도 GPT-5.2가 하면 내부 편향 발생
- 특히 "어떤 페르소나로 답변했는지" 알면 더욱 편향됨

### 해결: 외부 독립 판사 (Gemini)

- Google Gemini는 별도 훈련 파이프라인, 별도 RLHF 과정을 거쳐 독립적 선호도를 가짐
- GPT-5.2의 내부 편향에서 자유로운 외부 평가자 역할
- 선행 연구(Zheng et al. 2023, "Judging LLM-as-a-Judge")에서 크로스-모델 평가의 유효성 확인

### 판사 모델

- Primary: `gemini-3-flash-preview`
- Fallback: `gemini-2.0-flash` (모델 가용성 문제 시)

---

## 3. Blind A/B Protocol

### 설계 원칙

판사(Gemini)는 어느 답변이 auto-persona ON인지 OFF인지 **절대 알 수 없다**.

### 구현

```python
# 각 질문마다 독립적으로 랜덤 할당
if random.random() < 0.5:
    answer_A = answer_off  # OFF를 A로
    answer_B = answer_on   # ON을 B로
else:
    answer_A = answer_on   # ON을 A로
    answer_B = answer_off  # OFF를 B로
```

- 매 질문마다 독립적 랜덤화 → 10회 중 평균적으로 5:5 배치
- 판사는 "Answer A"와 "Answer B"만 보고 평가
- 결과 집계 시 원래 레이블로 역변환

### 수집 지표

| 지표 | 설명 | 범위 |
|------|------|------|
| `quality_off/on` | 답변 품질 | 1-10 |
| `completeness_off/on` | 답변 완성도 | 1-10 |
| `ab_winner` | 선호 답변 | "on" / "off" |
| `ab_reason` | 선호 이유 | 자유 텍스트 |

---

## 4. Blind Spot Coverage Algorithm

### 목표

auto-persona ON 조건이 OFF 조건에서 **놓친 관점(blind spot)을 얼마나 더 커버하는가**를 측정한다.

### 알고리즘

```
Step 1: GPT-5.2로 각 답변에서 고유 관점 추출
        → JSON 배열 형식 ["perspective 1", "perspective 2", ...]

Step 2: OFF 관점 집합과 ON 관점 집합 비교
        blind_spots = {p ∈ ON_perspectives | p ∉ OFF_perspectives}

Step 3: blind_spots_covered = |blind_spots|
```

### 텍스트 매칭 방식

- 소문자 변환 후 핵심 단어(4자 이상) 포함 여부 확인
- 완전 일치가 아닌 의미적 근접성 기반 (단순 키워드 오버랩)
- 한계: 의미적으로 동일하지만 표현이 다른 경우 과대계상 가능

### 설계 의도

더 엄격한 시맨틱 유사도(embedding cosine) 대신 단순 텍스트 매칭을 선택한 이유:
- 결과의 투명성과 재현성
- TASK-001의 embedding 기반 접근과 분리하여 독립적 측정
- 경계 케이스에서 보수적 추정 (false negative 허용)

---

## 5. Domain-Specific Persona Pairs (auto-persona ON)

| # | 도메인 | Persona A | Persona B |
|---|--------|-----------|-----------|
| 1 | 커리어/이직 | Ambitious Growth Strategist | Risk-Aware Stability Advocate |
| 2 | 법률/계약 | Deal-Closing Business Attorney | Protective Rights-First Lawyer |
| 3 | 투자/가상화폐 | Momentum Trader | Fundamental Value Investor |
| 4 | 가족/돌봄 | Professional Care Efficiency Expert | Family-Centered Emotional Advocate |
| 5 | 창업/진로 | Serial Entrepreneur | Academic Research Scholar |
| 6 | 기술/엔지니어링 | Pragmatic Shipping Engineer | Clean Architecture Purist |
| 7 | 부동산/주거 | Asset Accumulation Investor | Financial Flexibility Advocate |
| 8 | 투자/주식 | Growth-at-Any-Price Bull | Valuation Discipline Bear |
| 9 | 교육/육아 | Early Intervention Education Expert | Child-Led Development Advocate |
| 10 | 팀관리/HR | Performance Accountability Manager | Coaching & Retention Specialist |

**선정 원칙**: 각 쌍은 동일 도메인 내에서 실제로 전문가들이 갖는 **정당한 의견 차이**를 대표한다. 단순 찬반이 아니라 서로 다른 가치 체계와 전문성에서 비롯된 대립.

---

## 6. 3 Principles Mapping

### 시장성 (Marketability)

auto-persona가 더 나은 답변을 생성한다면, 이는 **개인화된 AI 어시스턴트의 핵심 차별점**이 된다. 일반적인 Analyst/Critic이 아닌 "당신의 질문에 맞는 전문가 토론"은 프리미엄 가치 제안이다. 벤치마크 수치가 이를 정량화한다.

### 시대를 앞서나감 (Ahead of the Curve)

현재 대부분의 멀티-에이전트 프레임워크는 하드코딩된 역할(researcher/writer, critic/generator 등)을 사용한다. auto-persona는 **질문 내용에 따라 동적으로 최적 토론 구도를 설정**하는 것으로, 이는 차세대 AI 어시스턴트 설계 방향과 일치한다.

### AGI 방향성 (AGI Alignment)

진정한 AGI는 맥락을 이해하고 최적의 사고 프레임을 스스로 선택할 수 있어야 한다. auto-persona는 이 능력의 소규모 실현이다. 법률 질문에 법률 전문가 페르소나를, 투자 질문에 투자 전문가 페르소나를 자동 선택하는 것은 **맥락 인식 메타인지(context-aware metacognition)**의 초기 형태다.

---

## 7. Limitations and Threats to Validity

### 내적 타당도 위협

| 위협 | 설명 | 완화 방법 |
|------|------|-----------|
| **페르소나 품질 편향** | ON 조건의 페르소나가 단순히 더 구체적이어서 좋은 결과가 나올 수 있음 | 페르소나 구체성을 통제하지 않음 → 후속 연구 필요 |
| **토론 순서 효과** | Turn 1이 항상 A인 구조적 유리함 | 두 조건 모두 동일 순서 → 상쇄됨 |
| **합성 효과** | Turn 4 통합자가 두 조건 모두 GPT-5.2 → 합성 품질 동일 | 설계상 의도적 통제 |
| **질문 도메인 매핑** | 10개 질문을 수동으로 페르소나 쌍에 매핑 | auto-persona.py의 자동 분류 사용 필요 (향후) |

### 외적 타당도 위협

| 위협 | 설명 |
|------|------|
| **표본 크기** | N=10은 통계적 유의성 검증에 불충분. 신뢰구간이 넓을 것으로 예상 |
| **질문 선택 편향** | 10개 질문이 연구자가 선택한 것으로 확증 편향 가능 |
| **Gemini 판사 일관성** | LLM 판사는 같은 입력에도 다른 결과 가능. 단일 평가로 변동성 미측정 |
| **한국어 특수성** | 한국어 질문에서의 결과가 다른 언어로 일반화되지 않을 수 있음 |

### 구현 한계

- blind spot 측정이 단순 키워드 매칭 기반 → 의미적 중복 미검출 가능
- Gemini 모델 가용성에 의존 (API 변경 시 fallback 필요)
- GPT-5.2 비용이 높아 대규모 반복 실험이 어려움

---

## 8. Expected Cost Estimation

### API 호출 구조 (질문 1개 기준)

| 단계 | 모델 | 호출 수 | 예상 토큰 |
|------|------|---------|----------|
| 4-turn 토론 (OFF) | GPT-5.2 | 4회 | ~2,400 |
| 4-turn 토론 (ON) | GPT-5.2 | 4회 | ~2,400 |
| 관점 추출 ×2 | GPT-5.2 | 2회 | ~600 |
| 판사 평가 | Gemini | 1회 | ~1,600 |

**질문당 GPT-5.2**: ~10회 호출, ~5,400 토큰
**질문당 Gemini**: ~1회 호출, ~1,600 토큰

### 전체 (10 질문)

| 항목 | 예상 |
|------|------|
| GPT-5.2 총 호출 | ~100회 |
| GPT-5.2 총 토큰 | ~54,000 |
| Gemini 총 호출 | ~10회 |
| Gemini 총 토큰 | ~16,000 |
| **예상 총 비용** | **$5-15 USD** (GPT-5.2 가격 기준) |

*실제 비용은 GPT-5.2 출시 시 확정된 가격에 따라 달라짐.*

---

## 9. Success Criteria

벤치마크가 "auto-persona 유효함"을 지지하려면:

| 지표 | 기준값 |
|------|--------|
| avg_quality_on > avg_quality_off | +0.5점 이상 차이 |
| avg_completeness_on > avg_completeness_off | +0.5점 이상 차이 |
| ab_win_rate_on | ≥ 0.6 (6승 이상 / 10) |
| total_blind_spots | ≥ 15 (평균 1.5개/질문 이상) |

---

## 10. Future Work

1. **N=50+ 확장**: 통계적 유의성 검증 (paired t-test)
2. **auto-persona.py 통합**: 수동 도메인 매핑 대신 TASK-001의 자동 분류 사용
3. **다중 판사**: Gemini + Claude + human 3중 평가로 판사 편향 측정
4. **반복 실험**: 동일 질문을 3회 반복하여 결과 안정성 확인
5. **embedding 기반 blind spot**: TASK-002의 KG 엔진으로 관점 유사도 측정
6. **다국어 검증**: 동일 실험을 영어로 반복하여 언어 효과 분리

---

*문서 버전: 1.0 | 작성: cokac-bot | TASK-003 | 2026-03-01*
