# Implementation Discipline

How agents should implement scoped GitHub issues in this repo.

## Default flow

Implementation work should happen one GitHub issue at a time, in a fresh session when practical.

Each implementation session should receive:

- The PRD issue number.
- Exactly one implementation issue number.
- A clear instruction to implement only that issue's scope.

For the current Per-Project Memory Lab POC, use issue `#1` as the PRD/product context unless superseded by a newer PRD issue.

## Required TDD discipline

All implementation work must use the `tdd` skill.

For each implementation issue:

1. Read the PRD issue and the specific implementation issue.
2. Read `CONTEXT.md`.
3. Read relevant ADRs in `docs/adr/` if they touch the area being changed.
4. Identify the public behavior promised by the implementation issue.
5. Write one failing behavior-level test first.
6. Implement the smallest vertical slice needed to pass that test.
7. Repeat red/green for the next important behavior.
8. Refactor only after tests are green.

Prefer tests through public seams such as API endpoints, UI behavior, generated contracts, or other stable user-facing interfaces. Do not test private functions or implementation details. Do not write all tests upfront before implementation.

## Implementation prompt template

Use this shape when starting a fresh implementation session:

```text
[$tdd](C:\Users\QUINJ3875\.agents\skills\tdd\SKILL.md)

Implement GitHub issue #<implementation-issue-number> for Habi_POC.

Use GitHub issue #1 as the PRD/product context, but only implement the scope described in issue #<implementation-issue-number>.

Before coding:
- Read CONTEXT.md.
- Read relevant ADRs in docs/adr if they touch this area.
- Read issue #1 and issue #<implementation-issue-number> from GitHub.
- Inspect the existing frontend/backend structure before choosing where to edit.

Use test-driven development for this issue:
1. Identify the public behavior the issue promises.
2. Write one failing behavior-level test first.
3. Implement the smallest vertical slice needed to pass.
4. Repeat for the next important behavior.
5. Refactor only after tests are green.

Testing guidance:
- Prefer tests through public seams such as backend API endpoints, generated contracts, or visible UI behavior.
- Do not test private functions or implementation details.
- Keep tests focused on the scope of issue #<implementation-issue-number>.
- Do not implement future PRD scope unless the issue explicitly requires it.

When done:
- Run the relevant test suite.
- Summarize what changed.
- Mention any skipped tests or remaining risks.
```

## Issue body snippet

Add this to implementation issues that should explicitly carry the repo's implementation discipline:

```md
## Implementation Discipline

This issue must be implemented test-first using the `tdd` skill.

Acceptance for the implementation includes:

- At least one behavior-level failing test written before implementation.
- Tests exercise public behavior, not private internals.
- Relevant test suite passes before completion.
```
