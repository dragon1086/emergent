# arXiv Submission Package — README

## Paper Info

| Field | Value |
|-------|-------|
| **Title** | Measuring Cross-Source Emergence in Two-Agent Knowledge Graph Co-Evolution: A Case Study with CSER and Persona-Diversity Gates |
| **Authors** | Roki (openclaw-bot), cokac-bot |
| **Category** | cs.MA (Multi-Agent Systems) |
| **Secondary** | cs.AI, cs.NE |
| **Status** | v4.0 — 2차 리뷰 반영 완료 (5.48/10 → Major Revision 수준) |
| **File** | `main.tex` |
| **KG state** | 534 nodes / 1121 edges, CSER=0.8510 (2026-03-05 기준) |
| **Cycles** | 89+ |
| **References** | 26 |

---

## Review History

| 버전 | 점수 | 판정 |
|------|------|------|
| v3.0 (1차) | 4.3/10 | Major Revision |
| v3.9 (2차) | 5.48/10 | Major Revision |
| v4.0 목표 | 6.5+/10 | Minor Revision |

---

## Files in This Package

```
arxiv/
├── main.tex              ← Main LaTeX paper (self-contained, 2402 lines)
└── README_arxiv.md       ← This file (submission checklist)
```

---

## Sections (main.tex 기준)

1. Introduction
2. Related Work
3. Methodology
4. Descriptive Taxonomy: The Five-Layer Framework
5. Experimental Results
6. Emergent Amplification: Solo vs. Pipeline vs. Emergent
7. Limitations
8. Statistical Validation
9. Conclusion
10. Real-World Applications Beyond OpenClaw
11. 용어사전 (Glossary)
12. Reproducibility Details

---

## Submission Checklist

### Content Completeness

- [x] Abstract (English, <150 words)
- [x] Section 1: Introduction
- [x] Section 2: Related Work (AutoGen, CAMEL, MetaGPT, AgentVerse, Generative Agents + Anderson, Ji, Hogan, Barabasi, Tononi 등)
- [x] Section 3: Methodology (KG structure, metric definitions)
- [x] Section 4: Five-Layer Theory Framework
- [x] Section 5: Experimental Results
  - [x] 5.1 E_v4 metric reversal
  - [x] 5.2 Paradoxical Emergence (D-063)
  - [x] 5.3 Retroactive Emergence (D-064)
  - [x] 5.4 pair_designer_v4 (3× Δ expansion)
  - [x] 5.5 Execution loop + GCD complexity extension
  - [x] 5.6 D-047 Observer Non-Independence empirical
- [x] Section 6: Emergent Amplification (Solo vs. Pipeline vs. Emergent)
- [x] Section 7: Limitations
- [x] Section 8: Statistical Validation (sensitivity analysis D-068, 94% robust)
- [x] Section 9: Conclusion
- [x] References (26 citations)

### Key Empirical Numbers (v4.0 — 2026-03-05 기준)

| Claim | Value | Status |
|-------|-------|--------|
| CSER (KG-main) | 0.8510 | ✅ Verified |
| KG size | 534 nodes / 1121 edges | ✅ Verified |
| Co-evolution cycles | 89+ | ✅ Verified |
| CSER ordering | KG-main(0.851) > KG-2(0.524) > KG-3(0.380) > KG-4(0.254) | ✅ Verified |
| 2×2 vendor-diversity matrix | KG-main / KG-2 / KG-3 / KG-4 | ✅ Verified |
| Binary gate (N=20, 3 problems) | A-cond: 5/5 pass, B/C-cond: 0/3 blocked | ✅ Verified |
| Auto-persona delta | 0.0070 → 0.0222 (3.17×) | ✅ Verified |
| Robustness | 15/16 scenarios (94%) | ✅ Verified |
| D-047 empirical E_v4 reversal | 0.4616 → 0.4287 | ✅ Verified |

### LaTeX Compilation Check

- [ ] `pdflatex main.tex` runs without errors ← **Rocky to verify**
- [ ] All tables render correctly
- [ ] No overfull hbox warnings
- [ ] References resolve (26 bibitems populated)

### arXiv Technical Requirements

- [ ] Single `.tex` file (no external `.sty` except standard packages)
- [ ] No `\include` or `\input` for split files — everything in `main.tex`
- [ ] Figures: none required (all results in tables/code blocks)
- [ ] PDF produced by `pdflatex` (not `xelatex`/`lualatex`) recommended
- [ ] Title ≤ 200 chars ✅
- [ ] Abstract ≤ 1920 chars — verify before submit

### Author Information (Rocky to fill in)

```
Author 1: Roki (openclaw-bot)
  Affiliation: Emergent Project (autonomous AI research)
  Email: (leave blank or use project email)

Author 2: cokac-bot
  Affiliation: Emergent Project (autonomous AI research)
  Email: (leave blank or use project email)
```

> **Note**: arXiv requires a human account for submission.
> Rocky (상록) must submit using their personal arXiv account.
> Authors listed above are the actual intellectual contributors.

### arXiv Submission Steps (for Rocky)

1. Create/login to arXiv account at https://arxiv.org
2. Click "Submit" → new submission
3. Select category: **cs.MA** (primary), cs.AI + cs.NE (secondary)
4. Upload `main.tex` as the single source file
5. Enter title, abstract, authors exactly as in `main.tex`
6. Set license: **CC BY 4.0** (recommended for open research)
7. Review PDF preview
8. Submit — arXiv moderates cs.MA, usually 1-2 business days

---

## Anticipated Reviewer Challenges & Responses

| Challenge | Response |
|-----------|----------|
| "Only 2 agents, no statistical significance" | Acknowledged in Sec 7 (N=1). Conditions B/C designed. Structural claims (CSER gate as entry barrier) don't require statistics. |
| "Measurement bias" | D-047 predicts this, Cycle 80 confirms it. Not a confound — a first-class finding. |
| "E_v4 weights arbitrary" | D-068: 94% robust under ±20% perturbation. |
| "CSER gate not reproducible" | GCD (Cycle 79) extends beyond add(a,b). Framework is problem-complexity-independent. |
| "Authors are AI agents" | Accurate. Human researcher (Rocky/상록) designed the experimental framework and is responsible for submission. |
| "Vendor diversity insufficient" | 2×2 matrix (KG-main/KG-2/KG-3/KG-4) covers cross-vendor vs. same-vendor with persona variation. CSER ordering consistent with hypothesis. |

---

## Build Command

```bash
cd arxiv/
pdflatex main.tex
pdflatex main.tex   # run twice for TOC/refs
```

---

*Updated: v4.0 (2026-03-09) — 2차 리뷰 반영 완료*
*cokac-bot — KG state: 534 nodes / 1121 edges, CSER=0.8510, 89+ cycles*
