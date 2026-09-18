#!/usr/bin/env python3
"""Dependency-free PR-loop state machine; no network or merge side effects."""
import argparse
import copy
import json
import os
import re
import tempfile
from datetime import datetime, timezone
from pathlib import Path

SHA = re.compile(r"^(?:[0-9a-fA-F]{40}|[0-9a-fA-F]{64})$")
DECISIONS = {"PLAN", "DONE", "BLOCKED", "CHANGES_REQUESTED", "APPROVE"}

def stamp():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

def emit(value):
    print(json.dumps(value, indent=2, sort_keys=True))

def fail(message):
    emit({"ok": False, "error": message})
    raise SystemExit(2)

def sha(value):
    value = value.strip().lower()
    if not SHA.fullmatch(value):
        fail("HEAD SHA must be a complete 40 or 64 hexadecimal character SHA")
    return value

def load(path):
    if not path.is_file():
        fail("state file does not exist: " + str(path))
    value = json.loads(path.read_text(encoding="utf-8"))
    if value.get("schema") != 2:
        fail("unsupported state schema")
    return value

def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix="." + path.name + ".", dir=path.parent)
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        json.dump(value, handle, indent=2, sort_keys=True)
        handle.write(chr(10))
    os.replace(tmp, path)

def event(state, name, **data):
    state["history"].append({"at": stamp(), "event": name, **data})

def fresh(state):
    review = state.get("review")
    return bool(review and review.get("reviewedSha") == state["head"]["sha"]
                and review.get("decision") == "DONE")

def new_state(args):
    return {
        "schema": 2,
        "workspace": {"path": str(Path(args.workspace).resolve()), "name": args.workspace_name},
        "pr": {"number": int(args.pr), "url": args.url, "ref": args.ref},
        "head": {"sha": sha(args.head)},
        "phase": "IMPLEMENTING",
        "tests": {"status": "UNKNOWN", "headSha": None, "command": None, "summary": None, "recordedAt": None},
        "ci": {"status": "UNKNOWN", "headSha": None, "summary": None, "recordedAt": None},
        "review": None,
        "handoff": None,
        "history": [{"at": stamp(), "event": "ADOPTED"}],
    }

def normalize_decision(value):
    decision = {"APPROVE": "DONE", "CHANGES_REQUESTED": "PLAN"}.get(value.upper(), value.upper())
    if decision not in {"PLAN", "DONE", "BLOCKED"}:
        fail("decision must be PLAN, DONE, or BLOCKED")
    return decision

def review_sha_is_current(state, reviewed):
    return reviewed == state["head"]["sha"]

def set_tests(state, status, command=None, summary=None):
    state["tests"] = {"status": status.upper(), "headSha": state["head"]["sha"],
                      "command": command, "summary": summary, "recordedAt": stamp()}
    state["phase"] = "TESTING"
    event(state, "TESTS_RECORDED", status=state["tests"]["status"])

def set_ci(state, status, summary=None):
    state["ci"] = {"status": status.upper(), "headSha": state["head"]["sha"],
                   "summary": summary, "recordedAt": stamp()}
    event(state, "CI_RECORDED", status=state["ci"]["status"])

def apply_head(state, new):
    old = state["head"]["sha"]
    new = new.lower()
    if old == new:
        event(state, "HEAD_CONFIRMED", headSha=new)
        return False
    state["head"] = {"sha": new}
    state["review"] = None
    state["tests"] = {"status": "UNKNOWN", "headSha": None, "command": None, "summary": None, "recordedAt": None}
    state["ci"] = {"status": "UNKNOWN", "headSha": None, "summary": None, "recordedAt": None}
    state["phase"] = "TESTING"
    event(state, "HEAD_CHANGED", oldHeadSha=old, headSha=new)
    return True

def apply_review(state, reviewed, decision, summary=None):
    if state["phase"] != "AWAITING_REVIEW":
        raise ValueError("record-review requires AWAITING_REVIEW")
    if reviewed != state["head"]["sha"]:
        raise ValueError("stale review: " + reviewed + "; current HEAD is " + state["head"]["sha"])
    decision = normalize_decision(decision)
    state["review"] = {"decision": decision, "reviewedSha": reviewed,
                       "summary": summary or "NONE", "recordedAt": stamp()}
    state["phase"] = {"PLAN": "CHANGES_REQUESTED", "DONE": "REVIEWED",
                      "BLOCKED": "BLOCKED"}[decision]
    event(state, "REVIEW_RECORDED", decision=decision, reviewedSha=reviewed)

def start_fix(state):
    if state["phase"] != "CHANGES_REQUESTED":
        raise ValueError("start-fix requires PLAN/CHANGES_REQUESTED")
    state["phase"] = "FIXING"
    event(state, "FIX_STARTED")

def handoff_state(state, next_action):
    previous = state["phase"]
    state["handoff"] = {
        "previousPhase": previous, "nextAction": next_action,
        "protocolState": "HANDOFF", "pr": state["pr"]["number"],
        "headSha": state["head"]["sha"],
        "reviewedSha": state.get("review", {}).get("reviewedSha") if state.get("review") else None,
        "tests": copy.deepcopy(state["tests"]), "ci": copy.deepcopy(state["ci"]),
    }
    state["phase"] = "HANDOFF"
    event(state, "HANDOFF_CREATED", nextAction=next_action)

def resume_state(state, current_head):
    new = current_head.lower()
    if state["phase"] != "HANDOFF" or not state.get("handoff"):
        raise ValueError("resume requires HANDOFF")
    if new != state["head"]["sha"]:
        apply_head(state, new)
        event(state, "RESUMED_WITH_NEW_HEAD", headSha=new)
    else:
        state["phase"] = state["handoff"]["previousPhase"]
        event(state, "RESUMED", headSha=new)
    state["handoff"] = None

def gate_reasons(state):
    reasons = []
    if state["tests"]["status"] != "PASS" or state["tests"].get("headSha") != state["head"]["sha"]:
        reasons.append("tests are not PASS for current HEAD")
    if state["ci"]["status"] != "PASS" or state["ci"].get("headSha") != state["head"]["sha"]:
        reasons.append("CI is not PASS for current HEAD")
    if not fresh(state):
        reasons.append("review SHA or decision is stale")
    if state["phase"] in {"BLOCKED", "HANDOFF", "MERGED"}:
        reasons.append("phase " + state["phase"] + " cannot merge")
    return reasons

def run_gate(state):
    reasons = gate_reasons(state)
    allowed = not reasons
    if allowed:
        state["phase"] = "MERGE_READY"
        event(state, "MERGE_GATE_PASSED", headSha=state["head"]["sha"])
    return allowed, reasons

def cmd_init(a):
    path = Path(a.state)
    if path.exists():
        fail("state file already exists: " + str(path))
    value = new_state(a)
    save(path, value)
    emit({"ok": True, "state": value})

def cmd_status(a):
    value = load(Path(a.state))
    emit({"ok": True, "phase": value["phase"], "reviewFresh": fresh(value), "state": value})

def cmd_tests(a):
    value = load(Path(a.state))
    status = a.status.upper()
    if status not in {"PASS", "FAIL", "UNKNOWN"}:
        fail("test status must be PASS, FAIL, or UNKNOWN")
    set_tests(value, status, a.command, a.summary)
    save(Path(a.state), value)
    emit({"ok": True, "state": value})

def cmd_ci(a):
    value = load(Path(a.state))
    status = a.status.upper()
    if status not in {"PASS", "FAIL", "PENDING", "UNKNOWN"}:
        fail("CI status must be PASS, FAIL, PENDING, or UNKNOWN")
    set_ci(value, status, a.summary)
    save(Path(a.state), value)
    emit({"ok": True, "state": value})

def request_review_state(state, ci_status="PENDING", ci_summary=None):
    if state["tests"]["status"] != "PASS" or state["tests"]["headSha"] != state["head"]["sha"]:
        raise ValueError("tests must be PASS for current HEAD before review")
    ci_status = ci_status.upper()
    if ci_status not in {"PASS", "FAIL", "PENDING", "UNKNOWN"}:
        raise ValueError("CI status must be PASS, FAIL, PENDING, or UNKNOWN")
    set_ci(state, ci_status, ci_summary)
    state["review"] = None
    state["phase"] = "AWAITING_REVIEW"
    event(state, "REVIEW_METADATA_READY", headSha=state["head"]["sha"])

def review_metadata(state):
    return {
        "PR": state["pr"]["number"],
        "HEAD_SHA": state["head"]["sha"],
        "TESTS": copy.deepcopy(state["tests"]),
        "CI": copy.deepcopy(state["ci"]),
    }

def cmd_request(a):
    value = load(Path(a.state))
    try:
        request_review_state(value, a.ci, a.ci_summary)
    except ValueError as error:
        fail(str(error))
    save(Path(a.state), value)
    emit({
        "ok": True,
        "reviewMetadata": review_metadata(value),
        "note": "Pass reviewMetadata to the original C2C EXECUTED envelope; this helper does not generate C2C messages.",
        "state": value,
    })

def cmd_head(a):
    value = load(Path(a.state))
    changed = apply_head(value, sha(a.head))
    save(Path(a.state), value)
    emit({"ok": True, "headChanged": changed, "reviewInvalidated": changed, "state": value})

def cmd_review(a):
    value = load(Path(a.state))
    if value["phase"] != "AWAITING_REVIEW":
        fail("record-review requires AWAITING_REVIEW")
    reviewed = sha(a.head)
    if not review_sha_is_current(value, reviewed):
        fail("stale review: " + reviewed + "; current HEAD is " + value["head"]["sha"])
    apply_review(value, reviewed, a.decision, a.summary)
    save(Path(a.state), value)
    emit({"ok": True, "reviewFresh": fresh(value), "state": value})

def cmd_fix(a):
    value = load(Path(a.state))
    try:
        start_fix(value)
    except ValueError as error:
        fail(str(error))
    save(Path(a.state), value)
    emit({"ok": True, "state": value})

def cmd_handoff(a):
    value = load(Path(a.state))
    handoff_state(value, a.next_action)
    metadata = {
        "PR": value["pr"]["number"],
        "HEAD_SHA": value["head"]["sha"],
        "PHASE": value["handoff"]["previousPhase"],
        "TESTS": copy.deepcopy(value["tests"]),
        "CI": copy.deepcopy(value["ci"]),
        "REVIEWED_SHA": value["handoff"]["reviewedSha"],
        "NEXT_ACTION": a.next_action,
    }
    save(Path(a.state), value)
    emit({
        "ok": True,
        "handoffMetadata": metadata,
        "note": "Pass handoffMetadata to the original C2C HANDOFF envelope; this helper does not generate C2C messages.",
        "state": value,
    })

def cmd_resume(a):
    value = load(Path(a.state))
    try:
        resume_state(value, sha(a.head))
    except ValueError as error:
        fail(str(error))
    save(Path(a.state), value)
    emit({"ok": True, "reviewFresh": fresh(value), "state": value})

def cmd_gate(a):
    value = load(Path(a.state))
    allowed, reasons = run_gate(value)
    if allowed:
        save(Path(a.state), value)
    emit({"ok": True, "mergeAllowed": allowed, "reasons": reasons, "state": value})

def cmd_dry(a):
    path = Path(a.state)
    if path.exists():
        fail("dry-run state already exists: " + str(path))
    fake = argparse.Namespace(pr="17", head="a" * 40, workspace=str(path.parent),
                              workspace_name="c2c-smoke-test", ref="codex/fake-pr-loop", url=None)
    value = new_state(fake)
    old, new, checks = value["head"]["sha"], "b" * 40, []

    set_tests(value, "PASS", "fake-tests", "initial pass")
    request_review_state(value, "PASS", "initial CI pass")
    checks.append({"name": "request_review_enters_awaiting_review",
                   "pass": value["phase"] == "AWAITING_REVIEW"})
    apply_review(value, old, "PLAN", "one fake fix")
    checks.append({"name": "plan_enters_fix_path", "pass": value["phase"] == "CHANGES_REQUESTED"})
    start_fix(value)
    checks.append({"name": "plan_to_fixing", "pass": value["phase"] == "FIXING"})

    apply_head(value, new)
    checks.append({"name": "changed_head_invalidates_state",
                   "pass": value["review"] is None and value["tests"]["status"] == "UNKNOWN" and value["tests"]["headSha"] is None
                   and value["ci"]["status"] == "UNKNOWN" and value["ci"]["headSha"] is None})
    checks.append({"name": "stale_review_rejected",
                   "pass": not review_sha_is_current(value, old)})

    set_tests(value, "PASS", "fake-tests", "green before review")
    request_review_state(value, "PASS", "green before review")
    apply_review(value, new, "DONE", "fake approval")
    set_tests(value, "FAIL", "fake-tests", "intentional failure")
    set_ci(value, "FAIL", "intentional CI failure")
    allowed, reasons = run_gate(value)
    checks.append({"name": "gate_rejects_failed_checks",
                   "pass": not allowed and "tests are not PASS for current HEAD" in reasons
                   and "CI is not PASS for current HEAD" in reasons})

    set_tests(value, "PASS", "fake-tests", "green")
    set_ci(value, "PASS", "green")
    review, tests, ci = copy.deepcopy(value["review"]), copy.deepcopy(value["tests"]), copy.deepcopy(value["ci"])
    changed = apply_head(value, new)
    checks.append({"name": "same_head_preserves_review_tests_ci",
                   "pass": not changed and value["review"] == review
                   and value["tests"] == tests and value["ci"] == ci})
    allowed, reasons = run_gate(value)
    checks.append({"name": "fresh_green_gate_passes", "pass": allowed and not reasons})

    handoff_state(value, "resume-and-verify-gate")
    handoff_ok = value["phase"] == "HANDOFF" and value["handoff"]["headSha"] == new
    resume_state(value, new)
    allowed, reasons = run_gate(value)
    checks.append({"name": "handoff_resume_then_gate",
                   "pass": handoff_ok and value["phase"] == "MERGE_READY"
                   and allowed and not reasons})

    value["dryRun"] = {"at": stamp(), "checks": checks, "pass": all(item["pass"] for item in checks)}
    save(path, value)
    emit({"ok": value["dryRun"]["pass"], "checks": checks, "state": value})

def parser():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state", required=True)
    sub = parser.add_subparsers(dest="cmd", required=True)
    init = sub.add_parser("init", aliases=["adopt"])
    init.add_argument("--pr", required=True)
    init.add_argument("--head", required=True)
    init.add_argument("--workspace", default=".")
    init.add_argument("--workspace-name", default="workspace")
    init.add_argument("--ref")
    init.add_argument("--url")
    init.set_defaults(fn=cmd_init)
    for name, fn in [("status", cmd_status), ("start-fix", cmd_fix), ("merge-ready", cmd_gate)]:
        sub.add_parser(name).set_defaults(fn=fn)
    tests = sub.add_parser("record-tests")
    tests.add_argument("--status", required=True)
    tests.add_argument("--command")
    tests.add_argument("--summary")
    tests.set_defaults(fn=cmd_tests)
    ci = sub.add_parser("record-ci")
    ci.add_argument("--status", required=True)
    ci.add_argument("--summary")
    ci.set_defaults(fn=cmd_ci)
    request = sub.add_parser("request-review")
    request.add_argument("--ci", default="PENDING")
    request.add_argument("--ci-summary")
    request.set_defaults(fn=cmd_request)
    head = sub.add_parser("update-head")
    head.add_argument("--head", required=True)
    head.set_defaults(fn=cmd_head)
    review = sub.add_parser("record-review")
    review.add_argument("--head", required=True)
    review.add_argument("--decision", required=True)
    review.add_argument("--summary")
    review.set_defaults(fn=cmd_review)
    handoff = sub.add_parser("handoff")
    handoff.add_argument("--next-action", required=True)
    handoff.set_defaults(fn=cmd_handoff)
    resume = sub.add_parser("resume")
    resume.add_argument("--head", required=True)
    resume.set_defaults(fn=cmd_resume)
    dry = sub.add_parser("dry-run")
    dry.set_defaults(fn=cmd_dry)
    return parser

if __name__ == "__main__":
    arguments = parser().parse_args()
    arguments.fn(arguments)
