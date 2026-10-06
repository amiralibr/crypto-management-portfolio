# MVP0 F4 Baseline Assessment v1.1

- **Assessment date:** 2026-10-06
- **Repository branch:** `arena/01a0fca1-crypto-management-portfolio`
- **Purpose:** Record the authorized F4 workspace preparation and documentation-only readiness state. This assessment does not grant start clearance.

## 1. Fetch and preflight

Fetched the approved annotated tag and the authorized branch without force, using explicit refspecs:

```text
git fetch --no-tags origin \
  refs/tags/f3-accepted:refs/tags/f3-accepted \
  refs/heads/arena/01a0fca1-crypto-management-portfolio:refs/remotes/origin/arena/01a0fca1-crypto-management-portfolio
```

Fetch succeeded. The fetched remote branch tip was exactly `c2bf56dea0f14e6cc4ee7052d7fbb9da9d5cadf4`.

Preflight checks, performed before restore or merge:

- Current branch: `arena/01a0fca1-crypto-management-portfolio` — PASS.
- HEAD: `e5ce70619b48922ad7ee09e4aec2d7b4ee19370b` (`OLD_HEAD`) — PASS.
- `refs/tags/f3-accepted^{commit}`: `9cf204d88fbcc1af0428331f866348a013f6aec0` (`BASELINE`) — PASS.
- Staged diff was empty — PASS.
- Tracked working-tree diff was only `M README.md` — PASS.
- `MVP0_F4_Baseline_Assessment_v1.0.md` existed as the sole untracked file — PASS.
- `OLD_HEAD` is an ancestor of the fixed `TARGET` `c2bf56dea0f14e6cc4ee7052d7fbb9da9d5cadf4` — PASS.
- `BASELINE` is an ancestor of the fixed `TARGET` — PASS.

The fixed TARGET SHA was used for ancestry checks and the fast-forward; `FETCH_HEAD` was not used as a target.

## 2. Protection of the existing local files

Immediately before restore, both working-tree files were reread and hashed. Their content matched the versions previously reported to the owner:

| File | Bytes | SHA-256 |
|---|---:|---|
| `README.md` | 2,857 | `cf6890c27ffc7d72eb9ba861690f6a16916778d4cf67b00c74865bf25d67487e` |
| `MVP0_F4_Baseline_Assessment_v1.0.md` | 78,137 | `1bcd18213add0d0f744c5d8d0383941548b757c2b8c90c7fa768f84286d85900` |

A supplemental no-clobber backup was created outside the repository in this execution at:

```text
/home/user/F4_pre_restore_backup_20261006_Qhpp2h/
```

The backup copies were compared byte-for-byte with the original files (`cmp` passed for both). Their sizes and SHA-256 values matched the table above. This local supplemental backup does not assert availability of any earlier external backup or of the previously missing 157-file set-aside; nothing was reconstructed from Git or remote sources.

## 3. README restore and fast-forward

Because HEAD equaled `OLD_HEAD` and the preflight and backup checks passed, only `README.md` was restored from `OLD_HEAD` with the authorized `git restore --source=... --worktree -- README.md` command. Both tracked and staged diffs were then empty.

The fast-forward command was:

```text
git merge --ff-only c2bf56dea0f14e6cc4ee7052d7fbb9da9d5cadf4
```

It succeeded as a fast-forward from `e5ce70619b48922ad7ee09e4aec2d7b4ee19370b` to `c2bf56dea0f14e6cc4ee7052d7fbb9da9d5cadf4`. No rollback, reset, clean, or force operation was performed.

## 4. Alignment evidence recorded immediately after the merge

The following was captured immediately after the successful fast-forward, before README review or documentation changes:

```text
$ git rev-parse HEAD
c2bf56dea0f14e6cc4ee7052d7fbb9da9d5cadf4

$ git status --short
?? MVP0_F4_Baseline_Assessment_v1.0.md

$ git diff --name-status
(empty)

$ git diff --cached --name-status
(empty)
```

Thus the recorded pre-documentation HEAD was exactly TARGET.

## 5. README status review and correction

The README at TARGET still described F2 as active and F3 as frozen/not started, which did not match the authorized phase-state record. The status block at the top of the README was corrected; the unrelated body and evidence links were left unchanged.

The resulting phase status is:

```text
F1/F2/F3: ACCEPTED — CLOSED
F4: AUTHORIZED — NOT STARTED — PENDING START CLEARANCE
F5/F6/F7: UNAUTHORIZED
```

## 6. Remaining untracked files

Before the documentation commit, `MVP0_F4_Baseline_Assessment_v1.0.md` remained untracked and unchanged. It is retained intentionally and is not included in the documentation commit. After the authorized documentation commit, it is expected to be the sole untracked file; the final `git status --short` is reported in the handoff.

No other unknown or conflicting untracked files were present at preflight. The supplemental backup is outside the repository and is not a Git working-tree file.

## 7. Scope and phase guardrails

- No F4 implementation or coding was started; no F4 pre-start clearance has been issued.
- This work is workspace preparation and documentation only. The documentation commit is restricted to this assessment and the README status correction.
- F5, F6, and F7 remain unauthorized.
- The documentation commit SHA is intentionally not stated here because it does not exist at assessment-authoring time. It will be reported after the commit; no amend will be used to insert its own SHA.
- Push outcome is reported in the handoff after the non-force push attempt.
