---
name: chatgpt-pr-loop
description: Run a SHA-verified PR implement, test, review, fix, rereview, and merge-gate workflow over one active Web ChatGPT conversation.
---

# ChatGPT PR Loop v2

This is the PR workflow layer. It does not replace or edit the upstream codex-with-chatgpt skill.

## Boundaries

The control plane is one local Codex session talking to one active Web ChatGPT conversation through the existing IAB transport. The data plane is the GitHub repository and pull request. GitHub is the formal source for the PR diff, remote branch, exact HEAD, checks, and review.

The upstream C2C skill owns local IAB message transport, long-chat continuity, checkpoints, and HANDOFF/new-chat transport. This skill owns PR adoption, SHA verification, test and CI evidence, the review/fix loop, conversation lineage metadata, the remote-GPT collaboration contract, and the local merge gate. `C2C` is a message envelope/transport concept; remote GPT must not be instructed to call a "C2C connector" for normal review.

MCP workspace access, a C2C bridge, a tunnel, OAuth pairing, and a doctor check are optional integrations. Their absence must not prevent local PR state work or GitHub-based review. Do not modify upstream C2C.

## Conversation lineage

Use a user-level registry at ~/.codex/chatgpt-pr-loop/<workspace>/state.json. It stores one active conversation and retained previous generations:

- active generation, URL, logical name, summary, and timestamps
- default logical name `<workspace> · G<NN> · <short summary>`
- previous[] for retained history
- current workspace, PR, exact HEAD, phase, tests, CI, and next action
- append-only local history

Bind an existing URL with scripts/conversation_registry.py bind; this starts G01 and does not require a new chat. Update work when moving between PRs without changing generation. A successful HANDOFF creates the next generation only after the new URL exists, the structured handoff is sent, and the new conversation acknowledges the current workspace and task. A failed handoff leaves the old active URL unchanged.

The default is one Codex session and one active Web ChatGPT conversation. A generation may cover multiple tasks and PRs. Create a new generation only for a long, lost, stale, or explicitly replaced conversation.

## Remote GPT contract and session bootstrap

The remote Web ChatGPT side does not automatically see this local skill. Give it a shared GitHub-readable contract:

- repository: `ZakuZakuu/chatgpt-pr-loop`
- path: `references/remote-gpt-contract.md`
- ref: `main`

For every newly created GPT generation, including a brand-new G01 when practical and every G<NN> HANDOFF, the first substantive message must point to that contract and require the remote GPT to read it through the GitHub connector before continuing. Do not paste the entire local SKILL.md into the chat.

Use this standard bootstrap/HANDOFF envelope:

```text
[C2C]
STATE: HANDOFF

SESSION: <workspace · GNN · short summary>
PREVIOUS_SESSION: <previous logical name or NONE>

CONTRACT_REPOSITORY: ZakuZakuu/chatgpt-pr-loop
CONTRACT_PATH: references/remote-gpt-contract.md
CONTRACT_REF: main

REPOSITORY: <owner/repo>
ORIGINAL_GOAL: <durable project/stage goal>
PROGRESS: <concise completed work>
CURRENT_TASK: <current task>
PR_NUMBER: <number or NONE>
HEAD_SHA: <exact full remote SHA or NONE>
PHASE: <current workflow phase>
TESTS: <current-head test status/summary>
CI: <current-head CI status/summary>
LAST_REVIEW: <PLAN/DONE/BLOCKED/NONE>
REVIEWED_SHA: <exact SHA or NONE>
KNOWN_ISSUES: <concise blockers/constraints or NONE>
NEXT_EXPECTED_STEP: <what the new GPT should do next>

INSTRUCTIONS:
1. First read the remote GPT contract from GitHub using the repository/path/ref above.
2. Treat GitHub PR + exact remote HEAD as the source of truth for code review.
3. C2C is the message envelope/transport, not a connector you should request.
4. Do not require MCP, a C2C connector, bridge, tunnel, or local workspace access for normal review.
5. Do not restart completed work; continue from the state above.
6. Acknowledge takeover with [C2C] STATE: HANDOFF, HANDOFF_STATUS: ACCEPTED, CONTRACT: LOADED, current PR/HEAD/phase, and NEXT_EXPECTED_STEP.
```

Do not swap the registry active URL/generation until the new conversation has loaded the contract and returned a coherent HANDOFF acknowledgement for the current workspace/task. If GitHub access is unavailable, keep the old generation active and treat takeover as failed/BLOCKED rather than silently proceeding under a different protocol.

## PR state and invariants

IMPLEMENTING -> TESTING -> AWAITING_REVIEW -> CHANGES_REQUESTED -> FIXING -> TESTING -> AWAITING_REVIEW -> REVIEWED -> MERGE_READY.

HANDOFF and BLOCKED are side states. Adopt an existing PR and existing remote HEAD; do not create a replacement PR during takeover.

Every iteration records PR number, full remote HEAD SHA, test result, and CI result. Test and CI records are bound to that exact HEAD. A same-HEAD refresh preserves review, tests, and CI. A changed push, rebase, amend, or force-push clears all three and returns to TESTING.

A normal review is accepted only from AWAITING_REVIEW and only when REVIEWED_SHA equals current remote HEAD SHA. An existing PLAN may be adopted through the separate `adopt-existing-review` command when its exact REVIEWED_SHA equals the adopted current HEAD; that path enters CHANGES_REQUESTED directly and does not weaken the normal `record-review` phase invariant. PLAN means fix, test, push, reread HEAD, and review again. DONE means the review is complete, not that merge is allowed. Merge readiness requires fresh DONE, PASS tests for the same HEAD, and either required CI PASS or explicit NOT_REQUIRED for the same HEAD. FAIL, PENDING, and UNKNOWN never satisfy the gate. This skill stops at MERGE_READY; merging is a separate explicitly authorized action.

## Procedure

1. Adopt the current PR, workspace, existing plan, and current remote HEAD. If an existing PLAN already has REVIEWED_SHA equal to that HEAD, use `adopt-existing-review` and continue at CHANGES_REQUESTED instead of requesting a duplicate review.
2. Implement or continue the requested work, run tests, and record evidence.
3. Commit and push; reread the exact remote HEAD.
4. Ask ChatGPT to review the GitHub PR at that exact SHA using the GitHub app/connector.
5. Record PLAN, DONE, or BLOCKED with REVIEWED_SHA and comments. Reject stale SHA or wrong-phase results.
6. For PLAN, continue fixing without asking the user, then repeat from step 2.
7. For DONE, refresh remote HEAD and evidence, then run the local merge gate.
8. If the conversation is too long or unavailable, create the next GPT generation and send the standard contract-aware HANDOFF/bootstrap envelope above. Swap the registry URL only after the new GPT has read `references/remote-gpt-contract.md` and acknowledged the current workspace/task.
9. Stop for product decisions, permissions, missing authorization, or genuine blockers.

## IAB/browser runtime recovery

Treat browser-control failure separately from conversation failure. A visible ChatGPT page with errors such as `nodeRepl.fetch request failed`, a stale browser handle, or a tab-control timeout may happen after sleep/resume or desktop runtime churn. It does not by itself mean that the active ChatGPT conversation is lost.

Before asking the user to refresh, restart Desktop, create a new conversation, or repair MCP/C2C infrastructure, perform this bounded recovery:

1. Preserve the current workspace registry, active conversation URL, generation, PR number, exact HEAD SHA, tests, CI, review state, and pending action. Do not change PR phase because of an IAB outage.
2. Do not HANDOFF and do not increment G<NN>. Opening the same conversation URL in a fresh browser or tab is still the same conversation generation.
3. Stop retrying a known-stale browser/tab handle. Reacquire IAB; if needed, create a fresh IAB browser/tab and navigate directly to the registry's exact active conversation URL.
4. Treat browser command timeouts as **unknown outcome**, not immediate failure. A create-tab, open-URL, navigation, or bind call may time out after the browser has already completed the action. After such a timeout:
   - do not immediately reset CUA/browser state;
   - wait a reasonable page-load grace period;
   - re-enumerate tabs once and look for the exact stored conversation URL;
   - if one or more matching tabs exist, reuse a single matching tab and stop creating more duplicates;
   - rebind that tab and verify control with a lightweight read such as URL/title/accessibility state before clicking or typing.
   Only after reconciliation confirms that no usable matching tab exists should a new tab be created.
5. Prefer preserving a live control session over resetting it on the first navigation timeout. A reset can discard the mouse/control handle even when the page itself loaded successfully. If a reset did occur, re-enumerate the surviving tabs and rebind the existing exact-URL tab before creating another.
6. Allow ChatGPT to finish loading before declaring bind/control failure. If the page visibly loads slowly, a login check, human verification, or conversation selection is blocking progress, wait for completion or ask the user only for that specific interactive step; do not restart the whole recovery flow.
7. Verify that the fresh/rebound tab is on the expected ChatGPT conversation and that the page/composer is controllable. Prefer the stored conversation URL over search, history guessing, or creating a new chat.
8. Before sending anything, determine whether the pending exact-HEAD request was already submitted:
   - if submission definitely never happened, send it once;
   - if submission status is uncertain, inspect the reopened conversation for the task/PR/HEAD marker first;
   - if the request is already present, do not send a duplicate.
9. Continue the existing review loop from the preserved state. Do not recreate connectors, rebuild tunnels, rerun unrelated work, open a replacement PR, or invalidate same-HEAD evidence.
10. Only if a fresh IAB handle/tab opened on the exact existing conversation URL still cannot be controlled should the workflow fall back to one user-assisted Desktop restart/manual relay. Do not repeatedly ask the user to refresh or restart without first trying the fresh-tab recovery.

A browser runtime outage is a transport incident, not a reason to abandon the active GPT conversation. Conversation rollover is reserved for genuine context/URL failure under the normal HANDOFF rules.

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
    python3 scripts/pr_loop.py --state /tmp/pr-state.json adopt-existing-review --reviewed-sha <full-sha> --decision PLAN
    python3 scripts/pr_loop.py --state /tmp/pr-state.json record-review --head <full-sha> --decision DONE
    python3 scripts/pr_loop.py --state /tmp/pr-state.json merge-ready

Validate with:

    python3 -m unittest discover -s tests -v
    python3 scripts/pr_loop.py --state /tmp/pr-loop-dry.json dry-run

Never store credentials, cookies, pairing codes, OAuth data, tunnel hosts, or full local secret configuration in repository state.
