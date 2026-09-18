# State schema

pr_loop.py stores local PR metadata. It is separate from C2C session state and never stores credentials, cookies, pairing codes, OAuth data, or temporary tunnel hosts.

## PR state

- schema: 2
- workspace: name and local path
- pr: number, URL, and ref
- head.sha: current exact 40 or 64 character remote HEAD
- phase: IMPLEMENTING, TESTING, AWAITING_REVIEW, CHANGES_REQUESTED, FIXING, REVIEWED, MERGE_READY, MERGED, HANDOFF, or BLOCKED
- tests: status, headSha, command, summary, timestamp
- ci: status, headSha, summary, timestamp
- review: decision, reviewedSha, summary, timestamp, or null
- handoff: previous phase, next action, PR, HEAD, review, tests, and CI snapshot
- history: append-only local events

Test, CI, and review evidence is fresh only for the current head.sha. Confirming the same HEAD preserves existing records. Changing HEAD clears review, test evidence, and CI evidence.

The merge gate requires current-head tests PASS, current-head CI PASS, review decision DONE, reviewedSha equal to head.sha, and phase is not BLOCKED, HANDOFF, or MERGED.

Passing the gate changes phase to MERGE_READY. A separately authorized operation would be required to merge.

## Conversation registry

conversation_registry.py stores one active Web ChatGPT conversation per workspace:

- active: generation, URL, logical name, summary, and timestamps
- previous[]: retained generations
- work: current workspace, PR, HEAD, phase, tests, CI, and next action
- history: bind, work update, and HANDOFF events

Binding an existing URL starts G01. Successful HANDOFF increments the generation after the new URL is known. Failed HANDOFF does not replace the active URL.
