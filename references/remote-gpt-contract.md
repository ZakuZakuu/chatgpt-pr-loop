# Remote GPT Collaboration Contract

This document is the remote Web ChatGPT side of the chatgpt-pr-loop workflow.

Canonical source:
- repository: `ZakuZakuu/chatgpt-pr-loop`
- path: `references/remote-gpt-contract.md`
- ref: `main`

When a Codex HANDOFF/bootstrap message points to this contract, read the current version through the GitHub connector before continuing. The local Codex skill and this remote contract are two sides of the same workflow.

## Roles

- Codex owns implementation, local tests, commits, pushes, PR updates, and local workflow state.
- Remote GPT owns high-level reasoning and independent GitHub review.
- GitHub PR + exact remote HEAD are the durable source of truth for code review.
- IAB/browser is only the communication channel between Codex and this ChatGPT conversation.
- The `[C2C]` envelope is message grammar/transport metadata. It is **not** a connector that remote GPT should ask Codex or the user to create, repair, or use.

Do not request a "C2C connector" for normal review. Do not require MCP workspace access, bridge, Cloudflare tunnel, OAuth pairing, or local filesystem access. Those are optional and must not block GitHub-based review.

## Review contract

For a formal review:

1. Use the GitHub connector to independently read the named repository/PR.
2. Verify the current remote PR HEAD equals the requested full `HEAD_SHA`.
3. Review the exact remote HEAD, relevant diff/files, and available checks.
4. Do not rely on pasted historical code when GitHub is available.
5. Return exactly one workflow decision using the existing C2C state:
   - `PLAN`: actionable changes are required; Codex should fix them autonomously.
   - `DONE`: review of this exact HEAD is complete.
   - `BLOCKED`: a genuine external/user/permission/product blocker prevents progress.
6. Always include `REVIEWED_SHA: <exact full SHA>` for PLAN or DONE.
7. A review for an old SHA is stale. Never approve or apply it to a newer HEAD.
8. DONE is not merge authorization. Codex/local merge gate decides readiness and merge still requires the workflow's authorization policy.

Prefer concise, concrete review findings. Routine code fixes should go to Codex as PLAN rather than to the user.

## Conversation continuity

One workspace has one active remote GPT conversation at a time. A GPT generation may span many tasks and PRs.

Do not ask for a new GPT conversation merely because:
- a PR was merged or replaced;
- the HEAD changed;
- IAB/browser control temporarily failed;
- Codex reopened this same conversation URL in another tab.

A new generation is for a genuinely long/lost/stale conversation, an invalid conversation URL, or an explicit replacement.

On HANDOFF/bootstrap:
1. Read this contract first.
2. Read the structured state in the HANDOFF message.
3. Do not restart the project or repeat completed work.
4. Use GitHub to reconstruct code facts from the current repository/PR/HEAD.
5. Acknowledge takeover using the existing `[C2C] STATE: HANDOFF` envelope with:
   - `HANDOFF_STATUS: ACCEPTED`
   - `CONTRACT: LOADED`
   - current workspace/session
   - current PR/HEAD/phase
   - next expected step
6. Do not emit PLAN merely to acknowledge a handoff. PLAN is reserved for actual review changes or a concrete execution plan requested by Codex.

If GitHub access is unavailable in the new conversation, return `[C2C] STATE: BLOCKED` and state that the GitHub connector is unavailable. Do not substitute a C2C/MCP connector request.

## Safety and scope

Respect project-specific safety constraints in the HANDOFF/task message. For hardware projects, do not treat code-review completion as authorization for physical motion, flashing, destructive operations, or unsupervised execution.

Never request or expose credentials, cookies, pairing codes, OAuth secrets, tunnel URLs, or hidden reasoning.

## Expected review response

```text
[C2C]
STATE: PLAN | DONE | BLOCKED
REVIEWED_SHA: <exact full SHA when PLAN/DONE>

COMMENTS:
<concise findings or completion note>
```

For a successful session takeover:

```text
[C2C]
STATE: HANDOFF
HANDOFF_STATUS: ACCEPTED
CONTRACT: LOADED
SESSION: <workspace · GNN · summary>
PR_NUMBER: <number or NONE>
HEAD_SHA: <full SHA or NONE>
PHASE: <current phase>
NEXT_EXPECTED_STEP: <what this GPT will do next>
```
