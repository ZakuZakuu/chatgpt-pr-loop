# State schema

This JSON is local PR metadata, not GitHub state or C2C session state. Never store credentials, cookies, pairing codes, or temporary tunnel URLs.

Fields:
- schema: 1
- workspace: path and name
- pr: number, URL, ref
- head: current exact 40 or 64 character SHA
- phase: IMPLEMENTING, TESTING, AWAITING_REVIEW, CHANGES_REQUESTED, FIXING, REVIEWED, MERGE_READY, MERGED, HANDOFF, or BLOCKED
- tests: status, command, summary, recordedAt
- ci: status, summary, recordedAt
- review: null or decision PLAN, DONE, or BLOCKED; reviewedSha, summary, recordedAt
- handoff: null or previousPhase, nextAction, PR/HEAD/test/CI metadata
- history: append-only local events

A review is fresh only when review.reviewedSha equals head.sha and decision is DONE. A changed HEAD clears review, tests, and CI; confirming the same HEAD preserves them. record-review accepts a result only from AWAITING_REVIEW.

Merge requires all of:
- head.sha equals review.reviewedSha
- review decision is DONE
- tests.status is PASS
- ci.status is PASS
- phase is not BLOCKED, HANDOFF, or MERGED

Passing the gate changes phase to MERGE_READY; a separate authorized operation changes it to MERGED.
