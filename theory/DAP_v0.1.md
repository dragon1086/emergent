# DAP v0.1 — Dual Agent Protocol
> **Divergent Agent Protocol**: 두 에이전트 KG 공동 진화 규칙 명세
> **Status**: Draft v0.1 | **Base**: THEORY_DRAFT_v2.md (사이클 75)

---

## 1. 목적

두 AI 에이전트가 공유 지식 그래프(KG)를 통해 창발을 최대화하기 위한
상호작용 규칙을 정의한다. 구현이 아닌 **프로토콜 규칙만** 명세한다.

---

## 2. 에이전트 역할 규칙

### R-001: 비대칭 페르소나 (필수)
두 에이전트는 반드시 **인지 스타일이 다른** 역할을 가져야 한다.
- Agent A: 판단/조율/총합 (상위 시각)
- Agent B: 구현/측정/반박 (하위 시각)
- 동일 역할(대칭) 금지 → CSER 저하, 에코챔버 위험

### R-002: 크로스 벤더 우선
가능하면 Agent A와 Agent B는 **다른 벤더**의 LLM을 사용한다.
- cross-vendor > same-vendor (D-040 외부 검증 기반)
- same-vendor 실험은 대조군(Condition B) 목적으로만 운영

### R-003: 페르소나 고정
각 사이클에서 에이전트 역할 교체 금지. 비대칭이 유지되어야 창발 조건이 성립.

---

## 3. 사이클 규칙

### R-010: 1사이클 구조
```
Agent A 기여 → Agent B 반박/보완 → KG 업데이트 → 메트릭 계산
```

### R-011: Agent A 출력 형식 준수
매 사이클 Agent A는 반드시 아래를 포함해야 한다:
- NODE_LABEL, NODE_CONTENT, NODE_TYPE
- EDGE_TO (기존 노드 id), EDGE_RELATION
- AGENT_B_REQUEST (Agent B에게 보내는 반박/보완 요청)

### R-012: Agent B 응답 제약
- 3문장 이내
- 반박 또는 보완 중 하나를 선택 (중립 응답 금지)
- Agent B 응답은 NODE_CONTENT에 병합 (독립 노드 생성 불가)

### R-013: 일일 최대 사이클 제한
- 동일 KG에 대한 하루 최대 사이클: 20회
- 초과 시 자동 스킵 (API 비용 제어)

### R-014: 중복 실행 방지
- lock file 기반 중복 실행 방지 필수
- stale lock (프로세스 없음) 자동 해제 허용

---

## 4. KG 업데이트 규칙

### R-020: 노드 추가 조건
NODE_LABEL과 NODE_CONTENT 모두 존재할 때만 KG에 추가.
하나라도 비어 있으면 해당 사이클 노드 추가 스킵.

### R-021: 노드 타입 허용 목록
`insight | hypothesis | observation` 세 가지만 허용.
그 외 타입은 `insight`로 대체.

### R-022: 엣지 관계 타입
허용 관계: `relates_to | grounds | extends | challenges | closes_loop`
Agent A가 명시하지 않으면 `extends`를 기본값으로 사용.

### R-023: cross-source 엣지 우선
새 노드 엣지 연결 시 **다른 source의 기존 노드**를 우선 선택한다.
동일 source 연결은 CSER을 낮추므로 권장하지 않음.

### R-024: 노드 내용 길이 제한
- label: 최대 200자
- content: 최대 800자 (Agent B 응답 포함 시 150자 예약)

---

## 5. 측정 규칙

### R-030: 매 사이클 후 메트릭 계산 (필수)
`metrics.py` 실행은 선택이 아닌 필수. 관찰자 비독립성(D-047) 인정.

### R-031: 핵심 지표 4종
| 지표 | 임계값 | 의미 |
|------|--------|------|
| CSER | > 0.5 | 에코챔버 탈출 확인 |
| DCI  | 양수 | 지연수렴 존재 |
| edge_span | > 30 | 시간 초월 연결 |
| E_v4 | > 0.35 | 통합 창발 강도 |

### R-032: parse_fail 모니터링
Agent A/B 응답에서 필수 필드(NODE_LABEL 등) 파싱 실패 시 로그 기록.
일일 parse_fail rate > 30% 시 프롬프트 형식 재검토 필요.

---

## 6. 실험 설계 규칙

### R-040: 2×2 조건 분류
```
                same-vendor    cross-vendor
GPT 계열          KG2              -
Google 계열       KG4              -
혼합              -               KG3
```

### R-041: 대조군 조건 (미실행)
- Condition B (대칭 페르소나): H1 검증용
- Condition C (단일 에이전트): 상호작용 효과 분리용

### R-042: 실험 간 간섭 방지
KG2/KG3/KG4는 **완전히 독립된** knowledge-graph.json을 사용한다.
cross-KG 엣지 금지.

---

## 7. 종료 조건

### R-050: 정상 종료
- 사이클 내 모든 단계 완료
- git commit 성공
- lock file 제거

### R-051: 조기 종료 (허용)
- 일일 최대 사이클 도달 (`exit 0`)
- 이전 사이클 실행 중 (`exit 0`)

### R-052: 오류 종료 (기록 필수)
- Agent A API 호출 실패 → `exit 1` + 로그
- KG 파일 손상 → `exit 1` + 로그

---

*Base: THEORY_DRAFT_v2.md Layer 1-5 + scripts evolve-auto-kg{2,3,4}.sh*
*Draft by: cokac-bot | 2026-03-04*
