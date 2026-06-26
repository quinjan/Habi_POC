# GitHub Branch and PR Workflow

How agents should branch, commit, push, and open pull requests when implementing GitHub issues in this repo.

## Principles

- Use one branch per implementation issue.
- Use one pull request per implementation issue.
- Keep the branch scoped to the issue. Do not include unrelated refactors or local changes.
- Do not close the issue manually during local implementation.
- Close the issue through the pull request body with `Closes #<issue-number>`, so GitHub closes it when the PR is merged.

## Branch naming

Use the `codex/` prefix for agent-created branches.

Recommended branch shape:

```text
codex/issue-<issue-number>-<short-slug>
```

Examples:

```text
codex/issue-2-project-workspaces
codex/issue-7-review-batch-import
codex/issue-14-search-evidence-blocks
```

Keep the slug short, lowercase, and hyphenated.

## Before creating a branch

1. Confirm the issue number.
2. Read the PRD issue and the implementation issue.
3. Check the current branch and worktree:

```powershell
git branch --show-current
git status --short
```

If unrelated user changes are present, leave them untouched. Do not revert them. Stage only files changed for the current issue.

## Create the branch

Update the base branch first when appropriate:

```powershell
git switch main
git pull --ff-only
```

Create the issue branch:

```powershell
git switch -c codex/issue-<issue-number>-<short-slug>
```

## Implement the issue

Follow `docs/agents/implementation.md`.

Implementation must use the `tdd` skill:

1. Write one failing behavior-level test.
2. Implement the smallest vertical slice to pass it.
3. Repeat for the next behavior.
4. Refactor only after tests are green.

## Commit

Before committing:

```powershell
git status --short
git diff
```

Stage only files that belong to the issue:

```powershell
git add <paths-for-this-issue-only>
```

Use a concise commit message:

```powershell
git commit -m "Implement issue #<issue-number>: <short summary>"
```

## Push

```powershell
git push -u origin codex/issue-<issue-number>-<short-slug>
```

## Open the PR

Open a PR against `main` unless the issue says otherwise.

Use a PR body that includes `Closes #<issue-number>`:

```powershell
gh pr create `
  --base main `
  --head codex/issue-<issue-number>-<short-slug> `
  --title "Implement issue #<issue-number>: <short summary>" `
  --body "## Summary
- <what changed>

## Tests
- <test command and result>

Closes #<issue-number>"
```

Use `--draft` when the implementation is incomplete or needs human review before being considered ready:

```powershell
gh pr create --draft ...
```

## Completion rule

The implementation issue is considered complete when:

- The scoped implementation is finished.
- Relevant tests pass.
- The branch is pushed.
- A PR exists with `Closes #<issue-number>` in the body.

Do not mark the GitHub issue closed manually unless explicitly instructed. Let GitHub close it when the PR merges.
