#!/usr/bin/env python3
"""
Phase 1: GPT-5.2가 혼자 못 푸는 문제 탐색

목표: 단일 호출 정답률 50~70% 구간의 어려운 문제 찾기
- 추론 집약 문제 (multi-step reasoning)
- 복합 시스템 설계 (여러 제약 동시 충족)
- 반례 발견이 어려운 문제 (edge case heavy)
"""
import json, os, urllib.request, time, sys
sys.stdout.reconfigure(line_buffering=True)

API_KEY = os.popen("grep OPENAI_API_KEY ~/.zshrc | head -1 | cut -d\"'\" -f2").read().strip()

def ask_gpt52(prompt, temperature=0.7):
    body = json.dumps({"model":"gpt-5.2","input":prompt,"temperature":temperature}).encode()
    req = urllib.request.Request("https://api.openai.com/v1/responses", data=body,
        headers={"Authorization":f"Bearer {API_KEY}","Content-Type":"application/json"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        r = json.loads(resp.read())
    for item in r.get("output",[]):
        if isinstance(item,dict) and item.get("type")=="message":
            for c in item.get("content",[]):
                if c.get("type")=="output_text":
                    code = c["text"].strip()
                    for pfx in ["```python","```"]:
                        if code.startswith(pfx): code=code[len(pfx):]
                    if code.endswith("```"): code=code[:-3]
                    return code.strip()
    return ""

# ── 난이도 높은 문제들 ──

PROBLEMS = [
    {
        "id": "concurrent_lru",
        "prompt": """Implement a thread-safe LRU cache in Python with these requirements:
- `get(key)` and `put(key, value)` must be O(1) amortized
- Must handle concurrent access from multiple threads correctly
- Must support a `snapshot()` method that returns a consistent view of all entries
- Use only stdlib (no external packages)
Class name: ConcurrentLRU(capacity: int)""",
        "test": lambda code: _test_concurrent_lru(code),
    },
    {
        "id": "interval_scheduling_weighted",
        "prompt": """Implement `max_weight_schedule(intervals: list[tuple[int,int,int]]) -> tuple[int, list[int]]`
Each interval is (start, end, weight). Find the maximum weight subset of non-overlapping intervals.
Return (total_weight, list_of_selected_indices).
Must handle up to 10000 intervals efficiently (O(n log n)).""",
        "test": lambda code: _test_weighted_scheduling(code),
    },
    {
        "id": "expression_parser",
        "prompt": """Implement `evaluate(expr: str) -> float` that parses and evaluates mathematical expressions.
Support: +, -, *, /, ** (power), unary minus, parentheses, nested parentheses.
Respect operator precedence: ** > unary - > * / > + -
** is right-associative. All others are left-associative.
Raise ValueError for invalid expressions.
No eval/exec/compile allowed.""",
        "test": lambda code: _test_expression_parser(code),
    },
    {
        "id": "graph_bridges",
        "prompt": """Implement `find_bridges(n: int, edges: list[tuple[int,int]]) -> list[tuple[int,int]]`
Find all bridges in an undirected graph. A bridge is an edge whose removal disconnects the graph.
n = number of nodes (0-indexed). edges = list of (u,v) pairs.
Return bridges as sorted list of (min(u,v), max(u,v)) tuples, sorted lexicographically.
Must be O(V+E) using Tarjan's algorithm.""",
        "test": lambda code: _test_bridges(code),
    },
    {
        "id": "regex_backref",
        "prompt": """Implement `match(pattern: str, text: str) -> bool`
Support standard regex: . * + ? | () for grouping
PLUS backreferences: \\1, \\2 etc. referring to captured groups.
Example: match(r'(a+)b\\1', 'aabaa') -> True (\\1 = 'aa')
Example: match(r'(a+)b\\1', 'aaba') -> False
No re module allowed.""",
        "test": lambda code: _test_regex_backref(code),
    },
    {
        "id": "serialize_graph",
        "prompt": """Implement serialize(graph) and deserialize(data) for arbitrary directed graphs.
graph = dict[str, list[str]] (adjacency list, may contain cycles).
serialize returns a string. deserialize returns the original graph.
Must handle: self-loops, cycles, disconnected components, empty graph, 
node names with special characters (spaces, commas, colons).
The serialization format must be unambiguous.""",
        "test": lambda code: _test_serialize_graph(code),
    },
]

def _safe_exec(code, timeout_s=5):
    ns = {}
    try:
        exec(code, ns)
        return ns
    except:
        return {}

def _test_concurrent_lru(code):
    ns = _safe_exec(code)
    C = ns.get("ConcurrentLRU")
    if not C: return 0
    p, t = 0, 5
    try:
        c = C(2); c.put(1,1); c.put(2,2)
        if c.get(1)==1: p+=1
        c.put(3,3)
        if c.get(2)==-1 or c.get(2) is None: p+=1
        # snapshot test
        s = c.snapshot()
        if isinstance(s, (dict,list)): p+=1
        # thread safety basic
        import threading
        errors = []
        def writer():
            try:
                for i in range(100): c.put(i, i)
            except Exception as e: errors.append(e)
        threads = [threading.Thread(target=writer) for _ in range(4)]
        for th in threads: th.start()
        for th in threads: th.join(timeout=5)
        if not errors: p+=1
        # still works after concurrent access
        c2 = C(1); c2.put(1,1); c2.put(2,2)
        if c2.get(1)==-1 or c2.get(1) is None: p+=1
    except: pass
    return p/t

def _test_weighted_scheduling(code):
    ns = _safe_exec(code)
    fn = ns.get("max_weight_schedule")
    if not fn: return 0
    p, t = 0, 4
    try:
        # Simple case
        w, sel = fn([(0,3,2),(1,5,4),(4,7,1),(6,8,3)])
        if w >= 5: p+=1  # optimal: (1,5,4)+(6,8,3)=7 or similar
        # Single
        w2, s2 = fn([(0,10,5)])
        if w2 == 5: p+=1
        # All overlap
        w3, s3 = fn([(0,10,1),(1,9,2),(2,8,3)])
        if w3 == 3: p+=1  # best single
        # Empty
        w4, s4 = fn([])
        if w4 == 0: p+=1
    except: pass
    return p/t

def _test_expression_parser(code):
    ns = _safe_exec(code)
    fn = ns.get("evaluate")
    if not fn: return 0
    p, t = 0, 7
    try:
        if abs(fn("2+3*4") - 14) < 0.01: p+=1
        if abs(fn("(2+3)*4") - 20) < 0.01: p+=1
        if abs(fn("2**3**2") - 512) < 0.01: p+=1  # right-assoc: 2^(3^2)=512
        if abs(fn("-3+4") - 1) < 0.01: p+=1
        if abs(fn("10/(2+3)") - 2) < 0.01: p+=1
        if abs(fn("-(2+3)") - (-5)) < 0.01: p+=1
        try:
            fn("2++3")  # may or may not be valid
            p += 0  # don't penalize
        except ValueError:
            p += 1
    except: pass
    return p/t

def _test_bridges(code):
    ns = _safe_exec(code)
    fn = ns.get("find_bridges")
    if not fn: return 0
    p, t = 0, 4
    try:
        # Simple bridge
        r = fn(4, [(0,1),(1,2),(2,3)])
        if set(map(tuple,r)) == {(0,1),(1,2),(2,3)}: p+=1
        # Cycle = no bridge
        r2 = fn(3, [(0,1),(1,2),(2,0)])
        if r2 == []: p+=1
        # Mixed
        r3 = fn(5, [(0,1),(1,2),(2,0),(2,3),(3,4)])
        expected = {(2,3),(3,4)}
        if set(map(tuple,r3)) == expected: p+=1
        # Single edge
        r4 = fn(2, [(0,1)])
        if set(map(tuple,r4)) == {(0,1)}: p+=1
    except: pass
    return p/t

def _test_regex_backref(code):
    ns = _safe_exec(code)
    fn = ns.get("match")
    if not fn: return 0
    p, t = 0, 5
    try:
        if fn(r'(a+)b\1', 'aabaa') == True: p+=1
        if fn(r'(a+)b\1', 'aaba') == False: p+=1
        if fn(r'(.).\1', 'aba') == True: p+=1
        if fn(r'(.).\1', 'abc') == False: p+=1
        if fn(r'a*b', 'aaab') == True: p+=1
    except: pass
    return p/t

def _test_serialize_graph(code):
    ns = _safe_exec(code)
    ser = ns.get("serialize")
    des = ns.get("deserialize")
    if not ser or not des: return 0
    p, t = 0, 4
    try:
        # Simple
        g = {"a":["b","c"],"b":["c"],"c":[]}
        if des(ser(g)) == g: p+=1
        # Cycle
        g2 = {"x":["y"],"y":["x"]}
        if des(ser(g2)) == g2: p+=1
        # Empty
        if des(ser({})) == {}: p+=1
        # Special chars
        g3 = {"a b":["c:d"],"c:d":[]}
        if des(ser(g3)) == g3: p+=1
    except: pass
    return p/t

# ── Run ──
N_TRIALS = 10
results = {}

for prob in PROBLEMS:
    pid = prob["id"]
    print(f"\n=== {pid} ===")
    scores = []
    for trial in range(N_TRIALS):
        try:
            code = ask_gpt52(prob["prompt"] + "\n\nReturn ONLY Python code, no markdown, no explanation.")
            score = prob["test"](code)
        except Exception as e:
            print(f"  t{trial+1}: ERR {e}")
            score = 0
        scores.append(score)
        s = "✅" if score >= 0.7 else "⚠️" if score > 0 else "❌"
        print(f"  t{trial+1}: {score:.2f} {s}")
        time.sleep(1)
    avg = sum(scores)/len(scores)
    pass_rate = sum(1 for s in scores if s >= 0.7) / len(scores)
    results[pid] = {"avg": avg, "pass_rate": pass_rate, "raw": scores}
    print(f"  → avg={avg:.3f} pass_rate={pass_rate:.0%}")

print(f"\n{'='*60}")
print("DISCOVERY SUMMARY: Problems where GPT-5.2 solo < 80%")
print(f"{'='*60}")
for pid, data in sorted(results.items(), key=lambda x: x[1]["avg"]):
    marker = "🎯 TARGET" if data["pass_rate"] < 0.8 else "too easy"
    print(f"  {pid}: avg={data['avg']:.3f} pass={data['pass_rate']:.0%} {marker}")

with open("/Users/rocky/emergent/experiments/benchmark_discovery_results.json","w") as f:
    json.dump(results, f, indent=2)
print("\nSaved.")
