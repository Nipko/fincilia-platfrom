from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any

TASK_RE = re.compile(r"FNC-[A-Z]+-\d{3}[A-Z]?")
SHORT_DEP_RE = re.compile(r"(?<!FNC-)([A-Z]+)-(\d{3})(?:\.\.(\d{3}))?")
DECISION_RE = re.compile(r"IMP-\d{3}")


@dataclass(frozen=True)
class Task:
    task_id: str
    section: str
    dependency_text: str
    status: str


@dataclass(frozen=True, order=True)
class Finding:
    code: str
    location: str
    message: str

    def as_dict(self) -> dict[str, str]:
        return {"code": self.code, "location": self.location, "message": self.message}


def normalize_status(value: str) -> str:
    value = value.strip().lower().replace(" ", "_").replace(":_human", "")
    return {"review": "review_pending", "in_progress": "in_progress"}.get(value, value)


def _cells(line: str) -> list[str]:
    return [cell.strip() for cell in line.strip().strip("|").split("|")]


def parse_backlog(text: str) -> tuple[list[Task], list[Finding]]:
    section = ""
    tasks: list[Task] = []
    findings: list[Finding] = []
    seen: dict[str, int] = {}
    for line_number, line in enumerate(text.splitlines(), start=1):
        if line.startswith("## "):
            section = line[3:].strip()
        if not re.match(r"^\|\s*FNC-", line):
            continue
        cells = _cells(line)
        task_id = cells[0]
        if task_id.startswith("FNC-EP-"):
            continue
        if not TASK_RE.fullmatch(task_id):
            findings.append(Finding("META-TASK-ID", f"backlog:{line_number}", f"invalid task ID {task_id}"))
            continue
        if task_id in seen:
            findings.append(Finding("META-DUPLICATE-TASK", f"backlog:{line_number}", f"also declared at line {seen[task_id]}"))
        seen[task_id] = line_number
        dependency_text = cells[2] if len(cells) >= 4 else ""
        status = normalize_status(cells[3]) if len(cells) >= 5 else "proposed"
        tasks.append(Task(task_id, section, dependency_text, status))
    return tasks, findings


def parse_frontmatter(text: str) -> dict[str, str]:
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}
    result: dict[str, str] = {}
    for line in lines[1:]:
        if line.strip() == "---":
            break
        match = re.match(r"^([a-zA-Z_]+):\s*(.*)$", line)
        if match:
            result[match.group(1)] = match.group(2).strip()
    return result


def dependency_ids(task: Task) -> set[str]:
    result: set[str] = set()
    for match in SHORT_DEP_RE.finditer(task.dependency_text):
        stream, start, end = match.groups()
        if end is None:
            result.add(f"FNC-{stream}-{start}")
            continue
        for number in range(int(start), int(end) + 1):
            result.add(f"FNC-{stream}-{number:03d}")
    for full in TASK_RE.findall(task.dependency_text):
        result.add(full)
    return result


def _path_overlap(left: str, right: str) -> bool:
    a = PurePosixPath(left.replace("\\", "/")).as_posix().rstrip("/")
    b = PurePosixPath(right.replace("\\", "/")).as_posix().rstrip("/")
    return a == b or a.startswith(b + "/") or b.startswith(a + "/")


def build_graph(root: Path, config: dict[str, Any]) -> tuple[dict[str, Task], dict[str, set[str]], list[Finding]]:
    sources = config["sources"]
    backlog_path = root / sources["backlog"]
    tasks, findings = parse_backlog(backlog_path.read_text(encoding="utf-8"))
    task_map = {task.task_id: task for task in tasks}
    edges = {task.task_id: dependency_ids(task) for task in tasks}

    for aggregate in config["aggregate_dependencies"]:
        target = aggregate["task"]
        selected = {
            task.task_id
            for task in tasks
            if task.section == aggregate["section"] and task.task_id not in aggregate["exclude"]
        }
        if target not in edges:
            findings.append(Finding("META-AGGREGATE-TARGET", "work-graph.json", f"unknown target {target}"))
        elif not selected:
            findings.append(Finding("META-AGGREGATE-EMPTY", "work-graph.json", f"selector for {target} is empty"))
        else:
            edges[target].update(selected)

    task_dir = root / sources["task_directory"]
    for path in sorted(task_dir.glob("FNC-*.md")):
        meta = parse_frontmatter(path.read_text(encoding="utf-8"))
        declared = meta.get("id") or meta.get("task")
        if declared != path.stem:
            findings.append(Finding("META-TASK-FILENAME", path.as_posix(), f"declares {declared!r}"))
            continue
        if declared not in task_map:
            parent = re.sub(r"[A-Z]$", "", declared)
            if parent not in task_map:
                findings.append(Finding("META-TASK-ORPHAN", path.as_posix(), f"{declared} is absent from backlog"))
                continue
            task_map[declared] = Task(declared, "Reconciliation subtask", parent, normalize_status(meta.get("status", "proposed")))
            edges[declared] = {parent}
        else:
            current = task_map[declared]
            task_map[declared] = Task(current.task_id, current.section, current.dependency_text, normalize_status(meta.get("status", current.status)))

    known = set(task_map)
    for task_id, dependencies in edges.items():
        for dependency in dependencies:
            if dependency not in known:
                findings.append(Finding("META-UNKNOWN-DEPENDENCY", task_id, dependency))

    return task_map, edges, findings


def topological_order(edges: dict[str, set[str]]) -> tuple[list[str], set[str]]:
    known = set(edges)
    remaining = {node: set(deps) & known for node, deps in edges.items()}
    order: list[str] = []
    while remaining:
        ready = sorted(node for node, deps in remaining.items() if not deps)
        if not ready:
            return order, set(remaining)
        for node in ready:
            order.append(node)
            remaining.pop(node)
        for deps in remaining.values():
            deps.difference_update(ready)
    return order, set()


def validate_repository(root: Path, config_override: dict[str, Any] | None = None) -> tuple[dict[str, Any], list[Finding]]:
    config_path = root / "docs/implementation/work-graph.json"
    config = config_override or json.loads(config_path.read_text(encoding="utf-8"))
    findings: list[Finding] = []
    required = {"sources", "states", "artifact_available_states", "aggregate_dependencies", "human_gates", "active_reservations"}
    missing = required - set(config)
    if missing:
        return {}, [Finding("META-CONFIG-MISSING", "work-graph.json", ", ".join(sorted(missing)))]

    task_map, edges, graph_findings = build_graph(root, config)
    findings.extend(graph_findings)
    allowed_states = set(config["states"])
    for task in task_map.values():
        if task.status not in allowed_states:
            findings.append(Finding("META-UNKNOWN-STATUS", task.task_id, task.status))

    order, cyclic = topological_order(edges)
    if cyclic:
        findings.append(Finding("META-DEPENDENCY-CYCLE", "work-graph.json", ", ".join(sorted(cyclic))))

    handoff_dir = root / config["sources"]["handoff_directory"]
    for task in task_map.values():
        if task.status in {"review_pending", "done"} and not (handoff_dir / f"{task.task_id}.md").is_file():
            findings.append(Finding("META-HANDOFF-MISSING", task.task_id, "review/done requires handoff"))

    reservations = config["active_reservations"]
    for index, left in enumerate(reservations):
        if left["task"] not in task_map:
            findings.append(Finding("META-RESERVATION-TASK", "work-graph.json", left["task"]))
        for right in reservations[index + 1 :]:
            for left_path in left["paths"]:
                for right_path in right["paths"]:
                    if _path_overlap(left_path, right_path):
                        findings.append(Finding("META-ROUTE-COLLISION", f"{left['task']}:{right['task']}", f"{left_path} <> {right_path}"))

    for gate in config["human_gates"]:
        if gate["task"] not in task_map or gate.get("agent_may_accept") is not False or not gate.get("required_roles"):
            findings.append(Finding("META-HUMAN-GATE", "work-graph.json", str(gate.get("task"))))

    decision_text = (root / config["sources"]["decisions"]).read_text(encoding="utf-8")
    decision_ids = DECISION_RE.findall(decision_text)
    if len(decision_ids) != len(set(decision_ids)):
        findings.append(Finding("META-DUPLICATE-DECISION", config["sources"]["decisions"], "decision IDs must be unique"))

    trace_text = (root / config["sources"]["traceability"]).read_text(encoding="utf-8")
    for reference in TASK_RE.findall(trace_text):
        if reference not in task_map:
            findings.append(Finding("META-TRACE-UNKNOWN-TASK", config["sources"]["traceability"], reference))

    available = set(config["artifact_available_states"])
    terminal = available | {"claimed", "in_progress", "blocked", "done"}
    next_candidates = sorted(
        task_id
        for task_id, task in task_map.items()
        if task.status not in terminal
        and all(task_map[dep].status in available for dep in edges.get(task_id, set()) if dep in task_map)
    )
    report = {
        "task_count": len(task_map),
        "edge_count": sum(len(value) for value in edges.values()),
        "decision_count": len(set(decision_ids)),
        "reservation_count": len(reservations),
        "topological_order": order,
        "next_candidates": next_candidates,
    }
    return report, sorted(set(findings))

