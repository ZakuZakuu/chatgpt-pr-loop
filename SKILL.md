---
name: chatgpt-pr-loop
description: Run a SHA-verified PR implement, test, review, fix, rereview, and merge-gate workflow over one active Web ChatGPT conversation.
---

# ChatGPT PR Loop v2

This is the PR workflow layer. It does not replace or edit the upstream codex-with-chatgpt skill.

## Boundaries

The control plane is one local Codex session talking to one active Web ChatGPT conversation through the existing IAB transport. The data plane is the GitHub repository and pull request. GitHub is the formal source for the PR diff, remote branch, exact HEAD, checks, and review.

The upstream C2C skill owns IAB message transport, long-chat continuity, checkpoints, and HANDOFF/new-chat transport. This skill owns PR adoption, SHA verification, test and CI evidence, the review/fix loop, conversation lineage metadata, and the local merge gate.

MCP workspace access, a C2C bridge, a tunnel, OAuth pairing, and a doctor check are optional integrations. Their absence must not prevent local PR state work or GitHub-based review. Do not modify upstream C2C.

## Conversation lineage

Use a user-level registry at ~/.codex/chatgpt-pr-loop/<workspace>/state.json. It stores one active conversation and retained previous generations:

- active generation, URL, logical name, summary, and timestamps
- previous[] for retained history
- current workspace, PR, exact HEAD, phase, tests, CI, and next action
- append-only local history

Bind an existing URL with scripts/conversation_registry.py bind; this starts G01 and does not require a new chat. Update work when moving between PRs without changing generation. A successful HANDOFF creates the next generation only after the new URL exists, the structured handoff is sent, and the new conversation acknowledges the current workspace and task. A failed handoff leaves the old active URL unchanged.

The default is one Codex session and one active Web ChatGPT conversation. A generation may cover multiple tasks and PRs. Create a new generation only for a long, lost, stale, or explicitly replaced conversation.

## PR state and invariants

IMPLEMENTING -> TESTING -> AWAITING_REVIEW -> CHANGES_REQUESTED -> FIXING -> TESTING -> AWAITING_REVIEW -> REVIEWED -> MERGE_READY.

HANDOFF and BLOCKED are side states. Adopt an existing PR and existing remote HEAD; do not create a replacement PR during takeover.

Every iteration records PR number, full remote HEAD SHA, test result, and CI result. Test and CI records are bound to that exact HEAD. A same-HEAD refresh preserves review, tests, and CI. A changed push, rebase, amend, or force-push clears all three and returns to TESTING.

A review is accepted only from AWAITING_REVIEW and only when REVIEWED_SHA equals current remote HEAD SHA. PLAN means fix, test, push, reread HEAD, and review again. DONE means the review is complete, not that merge is allowed. Merge readiness requires fresh DONE, PASS tests for the same HEAD, required CI PASS for the same HEAD, and the correct phase. This skill stops at MERGE_READY; merging is a separate explicitly authorized action.

## Procedure

1. Adopt the current PR, workspace, existing plan, and current remote HEAD.
2. Implement or continue the requested work, run tests, and record evidence.
3. Commit and push; reread the exact remote HEAD.
4. Ask ChatGPT to review the GitHub PR at that exact SHA using the GitHub app/connector.
5. Record PLAN, DONE, or BLOCKED with REVIEWED_SHA and comments. Reject stale SHA or wrong-phase results.
6. For PLAN, continue fixing without asking the user, then repeat from step 2.
7. For DONE, refresh remote HEAD and evidence, then run the local merge gate.
8. If the conversation is too long or unavailable, use the upstream C2C HANDOFF envelope with PR, full HEAD, phase, tests, CI, review SHA, and next action. Swap the registry URL only after successful takeover.
9. Stop for product decisions, permissions, missing authorization, or genuine blockers.

## Message contract

Use the upstream C2C envelope and its existing states: EXECUTED, PLAN, DONE, BLOCKED, and HANDOFF. This skill adds only review metadata:

- PR number
- exact HEAD_SHA
- TESTS status, command, and summary
- CI status and summary
- request for GitHub review of that exact remote HEAD

A review result carries REVIEWED_SHA, decision, test/CI observations, and concise comments. Do not invent a second message grammar.

## Commands

The scripts are dependency-free and do not contact GitHub, push, merge, or send messages:

    python3 scripts/pr_loop.py --state /tmp/pr-state.json adopt --pr 17 --head <full-sha> --workspace . --workspace-name demo
    python3 scripts/pr_loop.py --state /tmp/pr-state.json record-tests --status PASS --command '<tests>'
    python3 scripts/pr_loop.py --state /tmp/pr-state.json request-review --ci PASS
    python3 scripts/pr_loop.py --state /tmp/pr-state.json record-review --head <full-sha> --decision DONE
    python3 scripts/pr_loop.py --state /tmp/pr-state.json merge-ready

Validate with:

    python3 -m unittest discover -s tests -v
    python3 scripts/pr_loop.py --state /tmp/pr-loop-dry.json dry-run

Never store credentials, cookies, pairing codes, OAuth data, tunnel hosts, or full local secret configuration in repository state.
