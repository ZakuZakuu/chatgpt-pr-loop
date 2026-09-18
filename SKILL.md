---
name: chatgpt-pr-loop
description: Run a SHA-verified Codex implement, test, PR review, fix, rereview, and merge loop over the existing codex-with-chatgpt transport.
---

# ChatGPT PR Loop

Use this skill only for PR workflow. The original codex-with-chatgpt skill remains the owner of IAB, ChatGPT/MCP transport, pairing, long-chat or Project selection, checkpoints, HANDOFF, and new-chat takeover.

Do not edit the original C2C SKILL.md, protocol, connector, or message grammar. This skill owns only PR adoption, test/review records, fix iterations, and the merge gate.

## Invariants

- Adopt the named existing PR in place. Do not create a replacement PR unless asked.
- Record the PR number, URL, branch, exact remote HEAD SHA, tests, and CI before review.
- Every review request and result contains PR number, HEAD SHA, test result, and CI result.
- A review is valid only when its reviewed SHA exactly equals the current PR HEAD, represented by a complete 40 or 64 hexadecimal SHA. Any changed push, force-push, rebase, or amended commit clears the review.
- Re-confirming the same HEAD is a no-op for review, tests, and CI. It must not invalidate a valid review.
- ChatGPT PLAN means Codex fixes, tests, pushes, and requests review again. It is not a user blocker.
- ChatGPT DONE is not enough to merge. Current tests, required CI, and repository/user merge policy must pass.
- Never put credentials, cookies, pairing codes, or temporary tunnel URLs in state or ChatGPT messages.
- Stop for product decisions, permission changes, missing credentials, merge-policy ambiguity, or genuine blockers. Do not stop for routine review fixes.
- Do not merge without explicit merge authorization.

## State machine

Read references/state-schema.md for the JSON shape.

IMPLEMENTING -> TESTING -> AWAITING_REVIEW -> CHANGES_REQUESTED -> FIXING -> TESTING -> AWAITING_REVIEW -> REVIEWED -> MERGE_READY -> MERGED.

HANDOFF and BLOCKED are side states. A changed HEAD resets the phase to TESTING, clears review, and clears test/CI records. Re-confirming the same HEAD preserves all of them. MERGE_READY is only a gate result; it does not merge.

## Procedure

1. Adopt the named PR without changing unrelated branches or opening a new PR.
2. Implement and test. Record the command, status, and concise summary.
3. Push/update the existing PR and re-read the remote HEAD.
4. Ask ChatGPT, through the existing C2C connector, to review that exact PR HEAD through MCP.
5. Validate the returned SHA locally. Reject stale reviews.
6. For PLAN, fix, retest, push, record the new HEAD, and repeat.
7. For DONE, refresh HEAD, tests, and required CI before the merge gate.
8. If long-chat is too long or lost, invoke the original C2C HANDOFF. Carry PR number, current HEAD, phase, tests/CI, review SHA, and next action only. The new chat re-reads the current PR and workspace.
9. Merge only after the gate passes and authorization is clear.

## C2C message layer

The original C2C skill owns the complete message envelope and grammar. Do not make this helper generate a parallel protocol or a complete C2C message.

For a review request, provide these supplemental metadata fields to the original C2C EXECUTED state:

- PR number
- exact HEAD_SHA
- TESTS status, command, and summary
- CI status and summary
- request to review this exact HEAD

ChatGPT returns through the original protocol:

- PLAN: changes are requested; Codex continues the fix loop.
- DONE: review approval is complete; the local merge gate still runs.
- BLOCKED: a real blocker requires user attention.
- Include REVIEWED_SHA, test/CI observations, and concise comments as payload fields.

For a long-chat transition, provide PR number, current HEAD, phase, tests/CI, review SHA, and next action to the original C2C HANDOFF. The original C2C skill is responsible for [C2C] STATE: EXECUTED, [C2C] STATE: HANDOFF, ORIGINAL_GOAL, PROGRESS, CURRENT_STATE, KNOWN_ISSUES, and NEXT_EXPECTED_STEP.

The local helper is authoritative for SHA freshness and the merge gate. ChatGPT prose is not.

## Handoff and helper

Keep PR-loop state separate from C2C checkpoint/session state. A HANDOFF preserves PR number, current HEAD, phase, tests/CI, review SHA, and next action, but never diffs, file bodies, credentials, or tunnel URLs. On resume, fetch the PR HEAD again; a changed SHA invalidates the review.

scripts/pr_loop.py is dependency-free and never calls GitHub, pushes, merges, or sends messages. Use an explicit state path:

~~~text
python3 scripts/pr_loop.py --state dry-run/pr-loop-state.json dry-run
~~~

The dry-run executes the same transition helpers used by the CLI: PLAN -> FIXING, changed-HEAD invalidation, same-HEAD preservation, stale/failing gate rejection, fresh DONE approval, HANDOFF -> resume, and final gate success. Run it before wiring this workflow to a real PR.
