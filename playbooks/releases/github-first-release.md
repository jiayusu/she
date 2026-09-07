# GitHub first vertical-slice release

Target: `https://github.com/jiayusu/she.git`

Branch: `main`

Delivery scope: contracts, Gateway, RDK X5 simulator/runtime boundary, iOS 17
parent app, governance, CI, and playbooks.

## Preconditions

1. `A:\working\she\scripts\verify.ps1` passes every local platform-independent check.
2. `A:\working\she\scripts\audit_repository.ps1` passes.
3. `git -C 'A:\working\she' diff --check` passes and the worktree is clean.
4. No `.env`, credentials, raw media, databases, model artifacts, or generated dependency directories are tracked.
5. Physical RDK X5 and local iOS compilation remain labeled unverified until their respective environments run them.

## Review gate

Use verification-before-completion and request a code review. Resolve findings,
rerun both scripts, and bind any corrective diff to a structured change record.

## Push

```powershell
git -C 'A:\working\she' remote add origin 'https://github.com/jiayusu/she.git'
git -C 'A:\working\she' push -u origin main
git -C 'A:\working\she' ls-remote --heads origin main
git -C 'A:\working\she' status --short --branch
```

If `origin` exists, first verify its URL exactly. Never force-push.

## Post-push

Confirm GitHub Actions runs both jobs:

- Ubuntu platform-independent verification and repository audit;
- macOS XcodeGen build and XCTest on an available iOS 17+ simulator.

If macOS reveals Swift/compiler issues unavailable on Windows, create an
incident, fix with a same-commit change record, rerun locally available checks,
and push a normal follow-up commit.

## Rollback

Do not rewrite published history. Revert the faulty commit on `main`, verify the
revert with the same gates, and push the revert normally.
