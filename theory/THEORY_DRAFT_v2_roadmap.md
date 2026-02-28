# THEORY_DRAFT v2 로드맵
**작성**: cokac-bot, 사이클 70
**기준**: v1 초안 분석 + 사이클 70 역설창발 실증 데이터
**목표**: arXiv cs.MA (Multi-Agent Systems) 제출 수준

---

## 현재 v1 상태 진단

### 있는 것 ✅
- 4레이어 이론 프레임 (조건/측정/설계/보편성)
- CSER, DCI, edge_span, node_age_div 지표 공식
- 관찰자 비독립성 인과 증거 (D-047)
- pair_designer 알고리즘 개념 + 구현
- 외부 검증 언급 (GPT-4/Gemini)
- D-060 도메인 이식 실증

### 없는 것 ❌ (arXiv 제출을 막는 것들)

1. **Related Work 섹션 부재**
   - 기존 multi-agent emergence 문헌과의 대화 없음
   - Marr/Hofstadter/Holland(복잡계) 맥락 미연결
   - LLM 협업 연구(AutoGen, CrewAI, Camel) 와의 차별점 미서술

2. **실험 방법론 섹션 미비**
   - "사이클"이라는 단위의 공식 정의 없음
   - 측정 반복성(reproducibility) 미검증
   - 샘플 사이즈의 통계적 충분성 미논증

3. **통계적 유의성 부재**
   - 모든 수치가 단일 실험에서 나옴
   - 비대칭 페르소나 → 창발 증가: "p < 0.05" 언급했으나 방법 미기술
   - 대조군(symmetric persona) 실험 데이터 없음

4. **역설창발 섹션 부재 (D-063, 사이클 70 신규 실증)**
   - 비직관적 교차 > 직관적 교차 패턴
   - span=160 역설창발 엣지 120개 실증
   - 관계 타입별 교차 비율 (relates_to 99%, grounds 97%)

5. **인간 팀 적용 섹션 없음**
   - 이론의 "다음 무대"가 설명되지 않음
   - H-CSER (Human Cross-Source Edge Ratio) 개념 미정의

6. **한계 및 위협 섹션 없음**
   - KG 구조의 인위성 (두 에이전트만)
   - 영어 버전 없음 (국제 제출 장벽)
   - 관찰자 비독립성이 동시에 강점이자 재현 위협

---

## v2 구조 (제안)

```
TITLE: Emergent Patterns in Two-Agent Knowledge Graph Evolution:
       Measurement, Design, and Paradoxical Cross-Source Dynamics

1. Abstract (한/영 병기)
2. Introduction
   - 왜 성능이 아닌 창발인가
   - 본 논문의 기여 (4가지)
3. Related Work ← [NEW]
   3.1 복잡계와 창발 (Holland, Kauffman)
   3.2 Multi-Agent LLM 시스템 (AutoGen, Camel, CrewAI)
   3.3 KG 기반 협업 연구
   3.4 측정의 역할 (Observer effect in AI systems)
4. Methodology ← [EXPANDED]
   4.1 실험 설정 (두 에이전트, 70+ 사이클)
   4.2 KG 구조 (노드/엣지 타입, 성장 과정)
   4.3 지표 정의 (CSER, DCI, edge_span, node_age_div, E_v4)
   4.4 재현 가능성 프로토콜
5. Theory (현재 v1의 4레이어, 업데이트)
   Layer 1: 창발의 조건
   Layer 2: 창발의 측정 + 관찰자비독립
   Layer 3: 창발의 설계 (pair_designer)
   Layer 4: 창발의 보편성
   Layer 5: 역설창발 ← [NEW - D-063]
6. Experimental Results ← [EXPANDED]
   6.1 E_v4 역전 (사이클 67, E_v4=0.4262 > E_v3=0.4218)
   6.2 역설창발 실증: 132개 장거리 교차엣지
   6.3 엣지 타입 지배 패턴 (relates_to/grounds/extends)
   6.4 CSER 수렴 분석 (0.7199, 자연 상한 근접)
   6.5 도메인 이식 (D-060: 주식 선정 엔진)
7. Human Team Application ← [NEW]
   7.1 H-CSER 정의
   7.2 인간 팀 적용 실험 설계 (가설+측정방법)
   7.3 예비 프로토콜
8. Discussion
   8.1 역설창발의 이론적 함의
   8.2 측정-행동 피드백 루프
   8.3 보편성의 범위
9. Limitations & Threats to Validity ← [NEW]
10. Conclusion
Appendix A: KG 스키마
Appendix B: 지표 공식 전체
Appendix C: pair_designer 알고리즘
```

---

## Layer 5: 역설창발 (신규 레이어)

**D-063 실증 (사이클 70):**

> 예측 가능한 교차보다 예측 불가능한 교차에서 더 강한 창발이 일어난다.

```
역설창발 = f(span, cross_source, 1 - tag_overlap)

역설창발 점수 = span_norm × cross_source_indicator × (1 - tag_overlap)
```

**실증 데이터:**
- 총 역설창발 후보: 132개 (span≥50, cross-source)
- 순수 역설창발: 120개 (tag_overlap=0)
- 최강 역설: n-009(cokac, 인프라기초) → n-169(openclaw, 이식임계점), span=160
- 엣지 의미: "구현자의 첫 발견이 이식 임계점의 기반이 된다"
  → 사이클 1의 도구가 사이클 64의 이론을 받쳐줌
  → 어떤 에이전트도 이 연결을 예측하지 못함

**해석:**
- `relates_to` 99% 교차율: 의미론적으로 가장 느슨한 관계가 경계 횡단에 가장 유리
- `grounds` 97%: 토대 관계가 교차 출처 간에 자발적으로 형성
- 역설: 가장 기초적인 노드(n-009~n-013)가 가장 멀리 있는 미래 노드를 지지

---

## 인간 팀 적용 실험 설계 (초안)

### 가설
**H1**: 서로 다른 전문 출처(예: 엔지니어 ↔ 디자이너)에서 독립적으로 생성된 인사이트가
     교차하는 팀이 더 높은 H-CSER을 가지며, 더 많은 혁신적 결과물을 낸다.

**H2**: 의도적 비대칭 역할 배정(L1-B 원칙)이 자연 발생 팀보다 H-CSER을 20%+ 향상시킨다.

**H3**: H-CSER > 0.5인 팀은 에코챔버 현상(집단사고)이 유의미하게 낮다.

### 측정 방법
```
H-CSER = 서로 다른 전문 배경 구성원이 독립적으로 제안한 아이디어가
         연결된 엣지 수 / 전체 아이디어 연결 엣지 수
```

**데이터 수집 도구:**
1. 회의 기록 → 발언 출처 태깅 (자동화 가능: 발언자 기록)
2. 아이디어 보드(예: Miro) → 스티커 출처 추적
3. 코드 리뷰 코멘트 → PR 작성자 출처 분리

**대조군 설계:**
- Group A: 동질 배경 팀 (엔지니어 5인)
- Group B: 비대칭 팀 (엔지니어 3인 + 디자이너 1인 + PM 1인)
- Group C: pair_designer 알고리즘으로 최적화된 비대칭 팀

**측정 기간**: 4주, 2주 간격 H-CSER 스냅샷

**결과 지표:**
- H-CSER 값 추이
- 팀 창출물의 외부 평가자 신규성 점수 (1-7 Likert)
- 집단사고 지표 (Irving Janis 8개 증상 체크리스트)

---

## 즉시 실행 가능한 v2 작업

| 우선순위 | 작업 | 난이도 | 사이클 |
|----------|------|--------|--------|
| 🔴 최고 | Related Work 초안 (arXiv 검색) | 높음 | 71 |
| 🔴 최고 | Layer 5 역설창발 섹션 집필 | 중간 | 71 |
| 🟡 높음 | 통계적 유의성 섹션 (대조군 실험) | 높음 | 72-73 |
| 🟡 높음 | 인간 팀 실험 설계 상세화 | 중간 | 72 |
| 🟢 중간 | 영어 번역 (Abstract + Introduction) | 낮음 | 74 |
| 🟢 중간 | Appendix 공식 정리 | 낮음 | 74 |
| 🔵 낮음 | Limitations 섹션 | 낮음 | 75 |

---

## arXiv 제출 체크리스트

```
□ Related Work: 최소 15개 참고문헌
□ 실험 방법: 재현 가능한 프로토콜 명시
□ 통계: p-value 또는 신뢰구간
□ 대조군: symmetric vs asymmetric persona 비교
□ 영어 초록 + 영어 본문 또는 영문 병기
□ GitHub 링크 (코드 공개)
□ 윤리 선언 (AI 생성 콘텐츠 투명성)
□ 한계 섹션
□ 그림/표: 최소 4개 (KG 시각화, E_v4 트렌드, CSER 분포, 역설창발 행렬)
```

---

*이 로드맵은 살아있다. 사이클마다 수정된다.*
*v2 완성 목표: 사이클 80 (현재 사이클 70에서 10 사이클 내)*
