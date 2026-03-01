#!/usr/bin/env python3
"""
difficulty_ceiling_experiment.py — Difficulty Ceiling Experiment
Cycle 92, Task C1

Goal:
  Previous experiments used easy tasks (GCD, QuickSort, LRU) where quality=1.0
  always → ceiling effect. This experiment uses HARDER tasks where quality < 1.0,
  then measures if CSER↔quality correlation exists.

Tasks:
  1. Red-Black Tree insertion
  2. A* Pathfinding on weighted grid
  3. Mini Expression Compiler (variables, precedence, parentheses)

Conditions:
  A_heterogeneous:      냉정한 판사 × 집착하는 장인  → high CSER expected
  B_partial_homogeneous: 확신의 건축가 × 확신의 건축가 → low CSER expected

Usage:
  python difficulty_ceiling_experiment.py [--trials N] [--dry-run]
"""

import argparse
import json
import math
import os
import random
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path

# ─── Paths ────────────────────────────────────────────────────────────────────

REPO = Path(__file__).parent.parent
RESULTS_FILE = REPO / "experiments" / "difficulty_ceiling_results.json"
ENV_FILE = REPO / ".env"

# ─── Load .env ────────────────────────────────────────────────────────────────

def load_env():
    if ENV_FILE.exists():
        for line in ENV_FILE.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                os.environ.setdefault(k.strip(), v.strip())
    # Also pull from zshrc in case keys are there
    try:
        result = subprocess.run(
            ["zsh", "-c", "source ~/.zshrc && env"],
            capture_output=True, text=True, timeout=10
        )
        for line in result.stdout.split("\n"):
            if "=" in line:
                k, _, v = line.partition("=")
                os.environ.setdefault(k.strip(), v.strip())
    except Exception:
        pass

load_env()

OPENAI_KEY = os.environ.get("OPENAI_API_KEY", "")
GOOGLE_KEY = os.environ.get("GOOGLE_API_KEY", "")

# ─── Persona System Prompts ───────────────────────────────────────────────────

PERSONAS = {
    "냉정한 판사": (
        "You are a cold, impartial judge analyzing code solutions. "
        "Be dry, direct, data-only. Focus on correctness and edge cases. "
        "Challenge assumptions ruthlessly."
    ),
    "집착하는 장인": (
        "You are an obsessive craftsman who cares deeply about implementation details. "
        "Focus on elegance, efficiency, and completeness. Every line matters. "
        "Build solutions methodically."
    ),
    "확신의 건축가": (
        "You are a confident architect who sees the big picture. "
        "Declare the direction boldly. Focus on structure over details. "
        "Move fast with conviction."
    ),
}

CONDITIONS = {
    "A_heterogeneous": {
        "agent1_persona": "냉정한 판사",
        "agent2_persona": "집착하는 장인",
    },
    "B_partial_homogeneous": {
        "agent1_persona": "확신의 건축가",
        "agent2_persona": "확신의 건축가",
    },
}

# ─── Task Definitions ─────────────────────────────────────────────────────────

TASKS = {
    "red_black_tree": {
        "name": "Red-Black Tree Insertion",
        "prompt": (
            "Implement a Red-Black Tree with insertion in Python. "
            "Provide the complete implementation as a single Python class called `RedBlackTree`. "
            "The class must have:\n"
            "  - insert(key) method\n"
            "  - An internal Node class with: key, color ('R'/'B'), left, right, parent\n"
            "  - Proper rotations and color fixes after insertion\n"
            "Return ONLY the Python code in a ```python code block. No explanation."
        ),
        "total_tests": 10,
    },
    "a_star": {
        "name": "A* Pathfinding",
        "prompt": (
            "Implement A* pathfinding on a 2D grid in Python. "
            "Provide a single function called `astar(grid, start, end)` where:\n"
            "  - grid is a 2D list of integers (0=passable, 1=wall)\n"
            "  - start and end are (row, col) tuples\n"
            "  - Returns a list of (row, col) tuples representing the shortest path "
            "(including start and end), or None if no path exists\n"
            "  - Uses Manhattan distance as heuristic\n"
            "  - Handles diagonal moves: NO (4-directional only)\n"
            "Return ONLY the Python code in a ```python code block. No explanation."
        ),
        "total_tests": 5,
    },
    "mini_compiler": {
        "name": "Mini Expression Compiler",
        "prompt": (
            "Implement a mini expression evaluator in Python that handles:\n"
            "  - Integer literals\n"
            "  - Variables (single letters a-z, looked up in a dict)\n"
            "  - Operators: +, -, *, / (integer division)\n"
            "  - Parentheses for grouping\n"
            "  - Proper operator precedence (* and / before + and -)\n"
            "Provide a single function called `evaluate(expr, variables=None)` where:\n"
            "  - expr is a string expression\n"
            "  - variables is a dict mapping variable names to integer values\n"
            "  - Returns an integer result\n"
            "Return ONLY the Python code in a ```python code block. No explanation."
        ),
        "total_tests": 10,
    },
}

# ─── Quality Test Suites ──────────────────────────────────────────────────────

def test_red_black_tree(code: str) -> tuple[int, int]:
    """Run 10 RB-tree tests. Returns (passed, total)."""
    total = 10
    try:
        ns = {}
        exec(code, ns)
        RBT = ns.get("RedBlackTree")
        if RBT is None:
            return 0, total

        passed = 0

        def get_keys_inorder(tree):
            result = []
            def inorder(node):
                if node is None or node == tree.NIL:
                    return
                inorder(node.left)
                result.append(node.key)
                inorder(node.right)
            inorder(tree.root)
            return result

        def check_bst(tree):
            keys = get_keys_inorder(tree)
            return keys == sorted(keys)

        def check_root_black(tree):
            root = tree.root
            if root is None:
                return True
            nil = getattr(tree, "NIL", None)
            if root == nil:
                return True
            return root.color == "B"

        def check_no_red_red(tree):
            nil = getattr(tree, "NIL", None)
            def _check(node):
                if node is None or node == nil:
                    return True
                if node.color == "R":
                    lc = node.left.color if (node.left and node.left != nil) else "B"
                    rc = node.right.color if (node.right and node.right != nil) else "B"
                    if lc == "R" or rc == "R":
                        return False
                return _check(node.left) and _check(node.right)
            return _check(tree.root)

        def black_height(tree, node):
            nil = getattr(tree, "NIL", None)
            if node is None or node == nil:
                return 1
            lh = black_height(tree, node.left)
            rh = black_height(tree, node.right)
            if lh != rh or lh == -1:
                return -1
            return lh + (1 if node.color == "B" else 0)

        def check_equal_black_height(tree):
            return black_height(tree, tree.root) != -1

        # Test 1: Insert 10 elements, check BST property
        t = RBT()
        for k in [7, 3, 18, 10, 22, 8, 11, 26, 2, 6]:
            t.insert(k)
        if check_bst(t):
            passed += 1

        # Test 2: Root must be black
        if check_root_black(t):
            passed += 1

        # Test 3: No red-red parent-child
        if check_no_red_red(t):
            passed += 1

        # Test 4: Equal black height on all paths
        if check_equal_black_height(t):
            passed += 1

        # Test 5: In-order traversal correct after 10 inserts
        keys = get_keys_inorder(t)
        if keys == sorted([7, 3, 18, 10, 22, 8, 11, 26, 2, 6]):
            passed += 1

        # Test 6: Sequential inserts 1..7
        t2 = RBT()
        for k in range(1, 8):
            t2.insert(k)
        if check_bst(t2):
            passed += 1

        # Test 7: Root black after sequential inserts
        if check_root_black(t2):
            passed += 1

        # Test 8: No red-red after sequential inserts
        if check_no_red_red(t2):
            passed += 1

        # Test 9: Black height balanced after sequential inserts
        if check_equal_black_height(t2):
            passed += 1

        # Test 10: Duplicate insert does not crash
        try:
            t3 = RBT()
            for k in [5, 5, 5]:
                t3.insert(k)
            passed += 1
        except Exception:
            pass

        return passed, total

    except Exception:
        return 0, total


def test_a_star(code: str) -> tuple[int, int]:
    """Run 5 A* grid tests. Returns (passed, total)."""
    total = 5
    try:
        ns = {}
        exec(code, ns)
        astar = ns.get("astar")
        if astar is None:
            return 0, total

        passed = 0

        # Test 1: Simple 3x3 grid, direct path
        grid1 = [[0, 0, 0], [0, 0, 0], [0, 0, 0]]
        path = astar(grid1, (0, 0), (2, 2))
        if path and path[0] == (0, 0) and path[-1] == (2, 2) and len(path) == 5:
            passed += 1

        # Test 2: Wall blocking, must go around
        grid2 = [
            [0, 1, 0],
            [0, 1, 0],
            [0, 0, 0],
        ]
        path2 = astar(grid2, (0, 0), (0, 2))
        if path2 and path2[0] == (0, 0) and path2[-1] == (0, 2):
            passed += 1

        # Test 3: No path exists (fully walled)
        grid3 = [
            [0, 1],
            [1, 0],
        ]
        path3 = astar(grid3, (0, 0), (1, 1))
        if path3 is None:
            passed += 1

        # Test 4: Start == End returns path of length 1
        grid4 = [[0, 0], [0, 0]]
        path4 = astar(grid4, (0, 0), (0, 0))
        if path4 is not None and len(path4) == 1 and path4[0] == (0, 0):
            passed += 1

        # Test 5: 5x5 with obstacle corridor
        grid5 = [
            [0, 0, 0, 0, 0],
            [1, 1, 1, 1, 0],
            [0, 0, 0, 0, 0],
            [0, 1, 1, 1, 1],
            [0, 0, 0, 0, 0],
        ]
        path5 = astar(grid5, (0, 0), (4, 4))
        if path5 and path5[0] == (0, 0) and path5[-1] == (4, 4):
            # Verify path is valid (each step is adjacent, no walls)
            valid = True
            for i in range(len(path5) - 1):
                r1, c1 = path5[i]
                r2, c2 = path5[i + 1]
                if abs(r1 - r2) + abs(c1 - c2) != 1:
                    valid = False
                    break
                if grid5[r2][c2] == 1:
                    valid = False
                    break
            if valid:
                passed += 1

        return passed, total

    except Exception:
        return 0, total


def test_mini_compiler(code: str) -> tuple[int, int]:
    """Run 10 expression evaluation tests. Returns (passed, total)."""
    total = 10
    try:
        ns = {}
        exec(code, ns)
        evaluate = ns.get("evaluate")
        if evaluate is None:
            return 0, total

        passed = 0
        cases = [
            # (expr, variables, expected)
            ("2 + 3", None, 5),
            ("10 - 4", None, 6),
            ("3 * 4", None, 12),
            ("10 / 2", None, 5),
            ("2 + 3 * 4", None, 14),       # precedence: * before +
            ("(2 + 3) * 4", None, 20),     # parentheses override
            ("a + b", {"a": 3, "b": 7}, 10),
            ("a * b + c", {"a": 2, "b": 5, "c": 3}, 13),
            ("(a + b) * (c - d)", {"a": 1, "b": 2, "c": 5, "d": 3}, 6),
            ("a + b * c - d / e", {"a": 10, "b": 2, "c": 3, "d": 8, "e": 4}, 14),
        ]

        for expr, variables, expected in cases:
            try:
                result = evaluate(expr, variables) if variables is not None else evaluate(expr)
                if result == expected:
                    passed += 1
            except Exception:
                pass

        return passed, total

    except Exception:
        return 0, total


QUALITY_TESTERS = {
    "red_black_tree": test_red_black_tree,
    "a_star": test_a_star,
    "mini_compiler": test_mini_compiler,
}

# ─── CSER Calculation ─────────────────────────────────────────────────────────

def compute_cser(kg: dict) -> float:
    node_src = {n["id"]: n.get("source", "") for n in kg["nodes"]}
    cross = sum(
        1 for e in kg["edges"]
        if node_src.get(e["from"]) != node_src.get(e["to"])
    )
    return cross / len(kg["edges"]) if kg["edges"] else 0.0

# ─── Code Extraction ──────────────────────────────────────────────────────────

def extract_code(text: str) -> str:
    """Extract Python code from markdown code blocks or raw text."""
    if "```python" in text:
        return text.split("```python")[1].split("```")[0].strip()
    if "```" in text:
        return text.split("```")[1].split("```")[0].strip()
    return text.strip()

# ─── API Calls ────────────────────────────────────────────────────────────────

def call_openai(prompt: str, system: str, max_tokens: int = 1200, retries: int = 2) -> str:
    """Call OpenAI chat completions API."""
    url = "https://api.openai.com/v1/chat/completions"
    payload = json.dumps({
        "model": "gpt-5.2-chat-latest",
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ],
        "max_completion_tokens": max_tokens,
    }).encode()

    for attempt in range(retries + 1):
        try:
            req = urllib.request.Request(
                url, data=payload,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {OPENAI_KEY}",
                }
            )
            with urllib.request.urlopen(req, timeout=60) as resp:
                data = json.loads(resp.read())
                return data["choices"][0]["message"]["content"]
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="replace")[:200]
            if attempt < retries:
                print(f"    [OpenAI] HTTP {e.code} — retry {attempt + 1}/{retries}: {body}")
                time.sleep(3)
            else:
                raise RuntimeError(f"OpenAI HTTP {e.code}: {body}")
        except Exception as e:
            if attempt < retries:
                print(f"    [OpenAI] error — retry {attempt + 1}/{retries}: {e}")
                time.sleep(3)
            else:
                raise


def call_gemini(prompt: str, system: str, max_tokens: int = 1200, retries: int = 2) -> str:
    """Call Gemini API (optional fallback)."""
    model = "gemini-3.1-flash"
    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{model}:generateContent?key={GOOGLE_KEY}"
    )
    full_prompt = f"{system}\n\n{prompt}"
    payload = json.dumps({
        "contents": [{"parts": [{"text": full_prompt}]}],
        "generationConfig": {"maxOutputTokens": max_tokens},
    }).encode()

    for attempt in range(retries + 1):
        try:
            req = urllib.request.Request(
                url, data=payload,
                headers={"Content-Type": "application/json"}
            )
            with urllib.request.urlopen(req, timeout=60) as resp:
                data = json.loads(resp.read())
                return data["candidates"][0]["content"]["parts"][0]["text"]
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="replace")[:200]
            if attempt < retries:
                print(f"    [Gemini] HTTP {e.code} — retry {attempt + 1}/{retries}: {body}")
                time.sleep(3)
            else:
                raise RuntimeError(f"Gemini HTTP {e.code}: {body}")
        except Exception as e:
            if attempt < retries:
                print(f"    [Gemini] error — retry {attempt + 1}/{retries}: {e}")
                time.sleep(3)
            else:
                raise

# ─── Single Trial ─────────────────────────────────────────────────────────────

def run_trial(
    task_key: str,
    agent1_persona: str,
    agent2_persona: str,
    trial_num: int,
    dry_run: bool = False,
) -> dict:
    """
    Run one trial of the cycle:
      1. Agent1 proposes a solution approach (concept node)
      2. Agent2 reviews/extends it (connection edge)
      3. Final code generation
      4. Quality measurement
    Returns trial result dict.
    """
    task = TASKS[task_key]
    sys1 = PERSONAS[agent1_persona]
    sys2 = PERSONAS[agent2_persona]

    kg = {"nodes": [], "edges": []}

    if dry_run:
        # Simulate plausible results without API calls
        # Condition A (heterogeneous) should have higher quality and CSER
        is_hetero = agent1_persona != agent2_persona
        quality = round(random.uniform(0.45, 0.75) if is_hetero else random.uniform(0.20, 0.55), 4)
        cser = round(random.uniform(0.55, 0.85) if is_hetero else random.uniform(0.15, 0.45), 4)
        return {
            "trial": trial_num,
            "task": task_key,
            "quality": quality,
            "passed_tests": int(quality * task["total_tests"]),
            "total_tests": task["total_tests"],
            "cser": cser,
            "kg_nodes": 2,
            "kg_edges": 1,
            "dry_run": True,
        }

    # ── Step 1: Agent1 proposes solution approach ──────────────────────────
    prompt1 = (
        f"Task: {task['name']}\n\n"
        f"Propose a high-level solution approach for implementing this in Python. "
        f"Be specific about data structures, algorithm steps, and key invariants. "
        f"Keep it under 150 words."
    )
    try:
        resp1 = call_openai(prompt1, sys1, max_tokens=300)
    except Exception as e:
        resp1 = f"[Agent1 error: {e}]"

    node1 = {
        "id": f"n-{trial_num:02d}-a1",
        "source": "agent1",
        "persona": agent1_persona,
        "task": task_key,
        "content": resp1[:200],
    }
    kg["nodes"].append(node1)
    time.sleep(2)

    # ── Step 2: Agent2 reviews/extends (connection edge) ───────────────────
    prompt2 = (
        f"Task: {task['name']}\n\n"
        f"Agent1 proposed:\n{resp1[:300]}\n\n"
        f"Review this approach, identify gaps or improvements, and extend it with "
        f"specific implementation details. Keep it under 150 words."
    )
    try:
        resp2 = call_openai(prompt2, sys2, max_tokens=300)
    except Exception as e:
        resp2 = f"[Agent2 error: {e}]"

    node2 = {
        "id": f"n-{trial_num:02d}-a2",
        "source": "agent2",
        "persona": agent2_persona,
        "task": task_key,
        "content": resp2[:200],
    }
    kg["nodes"].append(node2)

    edge = {
        "from": node1["id"],
        "to": node2["id"],
    }
    kg["edges"].append(edge)
    time.sleep(2)

    # ── Step 3: Final code generation ──────────────────────────────────────
    code_prompt = (
        f"Based on this discussion:\n"
        f"Approach: {resp1[:200]}\n"
        f"Extension: {resp2[:200]}\n\n"
        f"{task['prompt']}"
    )
    # Agent1 generates final code (synthesizing both contributions)
    try:
        code_resp = call_openai(code_prompt, sys1, max_tokens=1200)
        code = extract_code(code_resp)
    except Exception as e:
        code = ""
        print(f"    [Code gen error trial {trial_num}]: {e}")
    time.sleep(2)

    # ── Step 4: Quality measurement ────────────────────────────────────────
    tester = QUALITY_TESTERS[task_key]
    passed, total = tester(code)
    quality = round(passed / total, 4)
    cser = compute_cser(kg)

    return {
        "trial": trial_num,
        "task": task_key,
        "quality": quality,
        "passed_tests": passed,
        "total_tests": total,
        "cser": cser,
        "kg_nodes": len(kg["nodes"]),
        "kg_edges": len(kg["edges"]),
        "dry_run": False,
    }

# ─── Pearson & Spearman Correlation ──────────────────────────────────────────

def pearson(xs: list[float], ys: list[float]) -> float:
    n = len(xs)
    if n < 2:
        return float("nan")
    mx = sum(xs) / n
    my = sum(ys) / n
    num = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    dx = math.sqrt(sum((x - mx) ** 2 for x in xs))
    dy = math.sqrt(sum((y - my) ** 2 for y in ys))
    if dx == 0 or dy == 0:
        return float("nan")
    return round(num / (dx * dy), 4)


def spearman(xs: list[float], ys: list[float]) -> float:
    def rank(lst):
        sorted_lst = sorted(enumerate(lst), key=lambda t: t[1])
        ranks = [0.0] * len(lst)
        i = 0
        while i < len(sorted_lst):
            j = i
            while j < len(sorted_lst) - 1 and sorted_lst[j + 1][1] == sorted_lst[i][1]:
                j += 1
            avg_rank = (i + j) / 2.0 + 1
            for k in range(i, j + 1):
                ranks[sorted_lst[k][0]] = avg_rank
            i = j + 1
        return ranks

    rx = rank(xs)
    ry = rank(ys)
    return pearson(rx, ry)

# ─── Run Condition ────────────────────────────────────────────────────────────

def run_condition(
    condition_key: str,
    n_trials: int,
    dry_run: bool,
) -> dict:
    cond = CONDITIONS[condition_key]
    agent1_persona = cond["agent1_persona"]
    agent2_persona = cond["agent2_persona"]

    print(f"\n{'='*60}")
    print(f"Condition: {condition_key}")
    print(f"  Agent1: {agent1_persona}")
    print(f"  Agent2: {agent2_persona}")
    print(f"  Trials per task: {n_trials}")
    print(f"{'='*60}")

    results_by_task = {}

    for task_key in TASKS:
        print(f"\n  Task: {TASKS[task_key]['name']}")
        trials = []
        for t in range(1, n_trials + 1):
            print(f"    Trial {t}/{n_trials}...", end=" ", flush=True)
            trial_result = run_trial(
                task_key=task_key,
                agent1_persona=agent1_persona,
                agent2_persona=agent2_persona,
                trial_num=t,
                dry_run=dry_run,
            )
            trials.append(trial_result)
            q = trial_result["quality"]
            c = trial_result["cser"]
            pts = trial_result["passed_tests"]
            tot = trial_result["total_tests"]
            print(f"quality={q:.3f} ({pts}/{tot}) cser={c:.3f}")

        avg_quality = round(sum(r["quality"] for r in trials) / len(trials), 4)
        avg_cser = round(sum(r["cser"] for r in trials) / len(trials), 4)
        results_by_task[task_key] = {
            "avg_quality": avg_quality,
            "avg_cser": avg_cser,
            "trials": trials,
        }
        print(f"  => {task_key}: avg_quality={avg_quality:.3f} avg_cser={avg_cser:.3f}")

    all_trials = [r for task_trials in results_by_task.values() for r in task_trials["trials"]]
    overall_avg_quality = round(
        sum(r["quality"] for r in all_trials) / len(all_trials), 4
    )
    overall_avg_cser = round(
        sum(r["cser"] for r in all_trials) / len(all_trials), 4
    )

    return {
        "personas": [agent1_persona, agent2_persona],
        "results_by_task": results_by_task,
        "overall_avg_quality": overall_avg_quality,
        "overall_avg_cser": overall_avg_cser,
    }

# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Difficulty Ceiling Experiment — Cycle 92 Task C1"
    )
    parser.add_argument(
        "--trials", type=int, default=5,
        help="Number of trials per task per condition (default: 5)"
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Simulate results without making API calls"
    )
    args = parser.parse_args()

    if not args.dry_run and not OPENAI_KEY:
        print("ERROR: OPENAI_API_KEY not set. Use --dry-run or set the key.")
        sys.exit(1)

    mode = "DRY RUN" if args.dry_run else "LIVE"
    print(f"\n{'='*60}")
    print(f"Difficulty Ceiling Experiment — Cycle 92 ({mode})")
    print(f"Tasks: Red-Black Tree | A* | Mini Compiler")
    print(f"Trials per task per condition: {args.trials}")
    print(f"{'='*60}")

    random.seed(92)

    condition_results = {}
    for cond_key in CONDITIONS:
        condition_results[cond_key] = run_condition(
            condition_key=cond_key,
            n_trials=args.trials,
            dry_run=args.dry_run,
        )

    # ── Correlation across all trials ──────────────────────────────────────
    all_cser_vals = []
    all_quality_vals = []
    for cond_data in condition_results.values():
        for task_data in cond_data["results_by_task"].values():
            for trial in task_data["trials"]:
                all_cser_vals.append(trial["cser"])
                all_quality_vals.append(trial["quality"])

    p_corr = pearson(all_cser_vals, all_quality_vals)
    s_corr = spearman(all_cser_vals, all_quality_vals)

    # Ceiling broken: at least one condition has avg_quality < 0.95
    ceiling_broken = any(
        cond["overall_avg_quality"] < 0.95
        for cond in condition_results.values()
    )

    # ── Summary ────────────────────────────────────────────────────────────
    print(f"\n{'='*60}")
    print("FINAL SUMMARY")
    print(f"{'='*60}")
    for cond_key, cond_data in condition_results.items():
        print(
            f"  {cond_key:<30} "
            f"quality={cond_data['overall_avg_quality']:.3f}  "
            f"cser={cond_data['overall_avg_cser']:.3f}"
        )
    print(f"\n  CSER vs Quality Pearson:  {p_corr:.4f}")
    print(f"  CSER vs Quality Spearman: {s_corr:.4f}")
    print(f"  Ceiling broken:           {ceiling_broken}")

    # ── Build output ───────────────────────────────────────────────────────
    output = {
        "experiment": "difficulty_ceiling",
        "cycle": 92,
        "tasks": list(TASKS.keys()),
        "n_trials": args.trials,
        "dry_run": args.dry_run,
        "conditions": condition_results,
        "correlation": {
            "cser_vs_quality_pearson": p_corr,
            "cser_vs_quality_spearman": s_corr,
            "ceiling_broken": ceiling_broken,
        },
        "timestamp": datetime.now().isoformat(),
    }

    with open(RESULTS_FILE, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print(f"\nSaved: {RESULTS_FILE}")
    return output


if __name__ == "__main__":
    main()
