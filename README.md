# chatgpt-pr-loop

chatgpt-pr-loop is a PR workflow layer for the original codex-with-chatgpt skill. It adopts an existing pull request and runs:

implement/test -> push -> ChatGPT review -> fix -> rereview -> merge gate

The original C2C skill remains responsible for IAB, MCP workspace access, long-chat continuity, checkpoints, and HANDOFF/new-chat takeover. This project is responsible only for PR adoption, exact HEAD verification, the review/fix loop, and the merge gate.

It uses the original C2C protocol (EXECUTED, PLAN, DONE, BLOCKED, and HANDOFF). It does not define a second PR-specific message protocol.

## Installation

Copy this directory to the user skill directory:

~/.codex/skills/chatgpt-pr-loop/

No package installation or additional runtime dependency is required.

## Basic use

Keep the state file outside the repository when practical. Adopt the current HEAD of an existing PR:

    python3 scripts/pr_loop.py --state /path/to/pr-loop-state.json init \
      --pr 123 \
      --head <full-40-or-64-character-head-sha> \
      --workspace /path/to/workspace \
      --workspace-name my-workspace \
      --ref feature/my-pr

Record tests and CI, then produce supplemental metadata for the original C2C EXECUTED review request:

    python3 scripts/pr_loop.py --state /path/to/pr-loop-state.json \
      record-tests --status PASS --command "<test command>" --summary "<summary>"
    python3 scripts/pr_loop.py --state /path/to/pr-loop-state.json \
      request-review --ci PENDING --ci-summary "<summary>"

Pass the returned PR, HEAD_SHA, TESTS, and CI metadata to the original C2C skill. Record ChatGPT's PLAN, DONE, or BLOCKED result with its exact REVIEWED_SHA. A changed HEAD invalidates the review; confirming the same HEAD preserves it.

Run the dependency-free local validation before installation:

    python3 scripts/pr_loop.py --state dry-run/pr-loop-state.json dry-run

The helper never contacts GitHub, pushes, merges, or sends ChatGPT messages. Those actions remain explicit workflow steps owned by the surrounding agent and the original C2C transport.

## Layout

- SKILL.md - workflow instructions
- agents/openai.yaml - skill metadata
- references/state-schema.md - local state contract
- scripts/pr_loop.py - dependency-free state machine and merge gate
