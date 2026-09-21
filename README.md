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

If an existing PLAN already reviewed the exact adopted HEAD, take it over explicitly without recording a second review:

    python3 scripts/pr_loop.py --state /tmp/pr-loop.json \
      adopt-existing-review --reviewed-sha <current-head-sha> --decision PLAN \
      --summary '<existing blocker>'
    python3 scripts/pr_loop.py --state /tmp/pr-loop.json start-fix

Use `--ci NOT_REQUIRED` when the repository has no required GitHub CI checks. `PASS` and `NOT_REQUIRED` satisfy the merge gate; `FAIL`, `PENDING`, and `UNKNOWN` do not. All evidence remains bound to the exact HEAD SHA.

Send the returned PR, HEAD_SHA, TESTS, and CI fields through the existing C2C envelope. Record the ChatGPT result only with the exact REVIEWED_SHA. A PLAN continues the fix loop. A fresh DONE plus same-HEAD green evidence produces MERGE_READY; this project does not auto-merge.

Conversation lineage is stored per workspace at:

    ~/.codex/chatgpt-pr-loop/<workspace>/state.json

The default logical name is `<workspace> · G<NN> · <short summary>`. Binding starts G01 with the supplied summary; a successful handoff creates the next generation with its new summary. Updating the PR or moving between PRs does not increment the generation.

Bind an existing ChatGPT URL to G01, update work across PRs without changing generation, and use the registry handoff command only after a new conversation has acknowledged the structured handoff. Failed handoff keeps the old active URL.

## Autonomy

After a workspace is enrolled and a GPT conversation is bound, normal loop traffic is standing-authorized. Codex should send exact-HEAD review requests, continue PLAN fixes, test, push, rerequest review, recover transport, and perform normal session handoff without asking the user to press "continue" at each step.

User confirmation is reserved for real decision/authorization boundaries such as product choices, credentials/permissions, paid or destructive actions, hardware safety gates, merge when explicitly required by policy, or genuine unresolved blockers.

## Remote GPT contract

Codex and remote Web ChatGPT use two views of the same workflow:

- local Codex: `SKILL.md`
- remote GPT: `references/remote-gpt-contract.md`

A newly created GPT generation is bootstrapped with a structured HANDOFF message containing the contract repository/path/ref plus the current repo, PR, exact HEAD, phase, tests/CI, last review, known issues, and next action. The remote GPT must read the contract through the GitHub connector before takeover is considered successful.

The contract explicitly defines C2C as message grammar/transport metadata, not a connector that remote GPT should request. Normal code review uses GitHub and the exact remote PR HEAD; MCP/bridge/tunnel/local-workspace access remain optional.

The local registry switches G01 -> G02 only after the new conversation has loaded the contract and acknowledged the handoff. If takeover fails, the previous generation remains active.

## IAB recovery

If ChatGPT remains visible but Codex loses browser control (for example `nodeRepl.fetch request failed` after sleep/resume), treat it as a stale IAB runtime/handle before treating it as a lost conversation:

- preserve the active conversation URL and current PR/HEAD state;
- do not HANDOFF, increment generation, rebuild MCP/tunnels, or create a new GPT conversation;
- abandon the stale handle, acquire a fresh IAB browser/tab, and open the exact stored conversation URL;
- treat create/open/bind timeouts as an unknown outcome: wait for loading, re-enumerate tabs, and reuse an exact-URL tab that may already have been created instead of resetting immediately or creating duplicates;
- avoid resetting CUA on the first navigation timeout because the page may already be loaded while only the RPC response timed out; if reset happened, rebind the surviving exact-URL tab;
- wait for slow page load or a specific human-verification/login step before declaring recovery failed;
- check whether the pending exact-HEAD request is already present before resending it;
- continue the same review loop once the fresh tab is controllable;
- ask for a Desktop restart or manual relay only after fresh-tab recovery also fails.

Opening the same conversation in a fresh tab is transport recovery, not a new conversation generation.

## Validation

    python3 -m unittest discover -s tests -v
    python3 scripts/pr_loop.py --state /tmp/pr-loop-dry.json dry-run

The scripts are dependency-free and have no network, push, merge, or ChatGPT side effects.
