# chatgpt-pr-loop

chatgpt-pr-loop is a small PR workflow layer for codex-with-chatgpt v2. It coordinates:

    Codex implement/test -> push/update PR -> ChatGPT review -> fix -> rereview -> merge gate

The upstream C2C layer remains responsible for IAB messaging, long-chat continuity, checkpoints, and HANDOFF transport. This project owns PR adoption, exact remote SHA verification, test and CI evidence, the review/fix loop, and the merge gate.

The control plane is Codex to one active Web ChatGPT conversation. The data plane is the GitHub repository and PR. MCP workspace access, a bridge, a tunnel, OAuth pairing, and doctor checks are optional integrations, not workflow prerequisites. Formal review uses the GitHub repository and exact PR HEAD.

## Install

Copy this directory to:

    ~/.codex/skills/chatgpt-pr-loop/

No package or additional runtime dependency is needed.

## Use

Adopt an existing PR:

    python3 scripts/pr_loop.py --state /tmp/pr-loop.json adopt \
      --pr 123 --head <full-40-or-64-character-sha> \
      --workspace /path/to/workspace --workspace-name my-workspace --ref feature

Record evidence and request review:

    python3 scripts/pr_loop.py --state /tmp/pr-loop.json \
      record-tests --status PASS --command '<test command>' --summary '<result>'
    python3 scripts/pr_loop.py --state /tmp/pr-loop.json \
      request-review --ci PASS --ci-summary '<required checks>'

Send the returned PR, HEAD_SHA, TESTS, and CI fields through the existing C2C envelope. Record the ChatGPT result only with the exact REVIEWED_SHA. A PLAN continues the fix loop. A fresh DONE plus same-HEAD green evidence produces MERGE_READY; this project does not auto-merge.

Conversation lineage is stored per workspace at:

    ~/.codex/chatgpt-pr-loop/<workspace>/state.json

Bind an existing ChatGPT URL to G01, update work across PRs without changing generation, and use the registry handoff command only after a new conversation has acknowledged the structured handoff. Failed handoff keeps the old active URL.

## Validation

    python3 -m unittest discover -s tests -v
    python3 scripts/pr_loop.py --state /tmp/pr-loop-dry.json dry-run

The scripts are dependency-free and have no network, push, merge, or ChatGPT side effects.
