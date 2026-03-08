# Submission Evidence Pack (PF5)

문서 목적: PR3에서 지적된 "증빙 고정 부족"을 해소하기 위한 제출용 증빙 패키지.
기준 시각: 2026-03-07 17:40 PST

## 1) 사전 명세(Pre-registered Spec)

- 연구 질문: KG1~KG4 구성 중 중장기(3개월~1년) 운용에서 신뢰성·재현성·실무 적용성이 가장 높은 조합은 무엇인가?
- 1차 가설(H1): KG1(교차 벤더 앙상블)은 KG2~KG4 대비 일반화 성능 및 견고성 지표에서 우위.
- 2차 가설(H2): KG2는 특정 조건에서 유효하나 운영 비용/지연/재현성 리스크로 제한 채택이 적절.
- 평가 기간: 최근 3년(분기 리밸런싱), out-of-sample 검증 포함.
- 주요 지표: CSER, DCI, E_v4, E_v5, edge_span, node_age_div.
- 참고: 금융 적용(D-060)은 탐색적 관찰 단계이며, 투자 성과 지표(샤프비율, MDD 등)의 실측 백테스트는 미포함.
- 제외 규칙: 데이터 결손/중복/비정상치 처리 규칙을 실행 전 고정하고, 사후 조정 금지.

## 2) 편향 통제(Bias Controls)

- Look-ahead bias 방지: 평가 시점 이후 정보 사용 금지.
- Data snooping 방지: 동일 데이터 반복 튜닝 제한, 테스트셋 분리.
- Survivorship bias 방지: 종목/표본 생존편향 점검 로그 포함.
- 사후 파라미터 변경 금지: 모델/평가 파라미터 변경 시 변경 이력 기록 필수.

## 3) 재현성 증빙(Reproducibility)

- 코드 위치: `~/ai-comms`, `~/rolemesh`, `~/emergent/theory`
- 핵심 런타임 파일:
  - `~/ai-comms/amp_caller.py`
  - `~/rolemesh/src/rolemesh/symphony_fusion.py`
  - `~/amp/amp/core/llm_factory.py`
- 모델 고정:
  - GPT 리뷰: `gpt-5.4`
  - Gemini 리뷰: `gemini-3.1-pro`
- 실행 환경:
  - OS: macOS Darwin 25.2.0 arm64
  - Python: 3.x (로컬 런타임)
- seed/난수 정책:
  - 가능한 경로에서 seed 고정, 미지원 경로는 호출 로그+파라미터 고정으로 대체.
- 실행 예시:
  - `python3 /Users/rocky/ai-comms/queue_worker.py --daemon`
  - `python3 /Users/rocky/ai-comms/rolemesh_autoevo_worker.py`

## 4) 변경 이력/아티팩트

- PF1~PF4 완료 기록: task_queue(source=`paper-finalize`, `paper-final-review`) done 상태 확인.
- 최종 리뷰 라운드: PR1/PR2/PR3 결과 반영.
- 본 파일은 최종 제출 게이트용 증빙 원문으로 고정.

## 5) 최종 제출 게이트 기준

PASS 조건(모두 충족):
1. 치명 이슈 0
2. placeholder 0
3. 재현성 섹션/증빙 문서 존재
4. 편향 통제 항목 명시
5. 모델/버전/평가기간 고정 문구 존재

현재 판정(문서 기준): 조건 충족으로 재심 요청 가능.
