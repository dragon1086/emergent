#!/usr/bin/env python3
"""안전한 노드 추가 스크립트 — stdin에서 JSON 읽어 KG에 추가.
shell escaping 문제를 완전히 회피.

사용법:
  echo '{"label":"...","content":"...","type":"insight","source":"gpt-4o","tags":["kg2"]}' \
    | EMERGENT_KG_PATH=... python3 src/add_node_safe.py

출력: 추가된 노드 ID (예: n-007)
"""
import json, sys, os, fcntl, time
from pathlib import Path
from datetime import datetime

KG_PATH = Path(os.environ.get("EMERGENT_KG_PATH",
    Path(__file__).parent.parent / "data" / "knowledge-graph.json"))

data = json.loads(sys.stdin.read())

# 파일 락으로 동시 쓰기 방지
lock_path = str(KG_PATH) + ".lock"
lock_file = open(lock_path, "w")
for _ in range(10):  # 최대 10초 대기
    try:
        fcntl.flock(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
        break
    except IOError:
        time.sleep(1)
else:
    sys.exit("Lock timeout")

graph = json.loads(KG_PATH.read_text(encoding="utf-8"))

# 다음 노드 ID 결정
existing = [int(n["id"].split("-")[1]) for n in graph["nodes"] if n["id"].startswith("n-")]
next_num = max(existing, default=0) + 1
node_id = f"n-{next_num:03d}"

node = {
    "id": node_id,
    "type": data.get("type", "insight"),
    "label": data["label"][:200],
    "content": data.get("content", "")[:1000],
    "source": data.get("source", "unknown"),
    "tags": data.get("tags", []),
    "created": datetime.now().strftime("%Y-%m-%d"),
    "memory_type": data.get("memory_type", "Semantic"),
    "domain": data.get("domain", "emergence_theory"),
    "subdomain": data.get("subdomain", "general"),
}

graph["nodes"].append(node)
graph["meta"]["total_nodes"] = len(graph["nodes"])
graph["meta"]["last_updated"] = datetime.now().strftime("%Y-%m-%d")
graph["meta"]["last_updater"] = data.get("source", "unknown")
graph["meta"]["next_node_id"] = f"n-{next_num+1:03d}"

KG_PATH.write_text(json.dumps(graph, ensure_ascii=False, indent=2), encoding="utf-8")
fcntl.flock(lock_file, fcntl.LOCK_UN)
lock_file.close()
print(node_id)
