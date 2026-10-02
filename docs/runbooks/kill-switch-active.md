# Runbook: Kill Switch Activated

## Symptoms

- Kill Switch state is active
- New orders are rejected
- Dashboard or alert indicates emergency state

## Immediate Actions

1. Confirm activation source and reason.
2. Check active orders, partial fills, positions, and Synthetic Stops.
3. Confirm new orders are blocked.
4. Cancel open orders if connector is available.
5. Mark affected items as MANUAL_REVIEW if connector is unavailable.
6. Do not resume before root-cause analysis.

## Escalation

- Operator verifies state and collects evidence.
- Admin approves recovery action.
- Admin + Operator approval is required for resume.

## Resume Criteria

- Root cause documented.
- Orders, fills, positions, and stops reconciled.
- No unresolved critical discrepancy.
- Risk limits are safe.
- Two-Person Approval completed.
- Reduced exposure applied.

## Post-Incident

- Record activation, source, reason, affected entities, and recovery time.
- Add tests or monitoring improvement for identified gaps.
