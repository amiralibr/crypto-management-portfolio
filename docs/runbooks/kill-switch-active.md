# Runbook: Kill Switch Activated

## Service & Routing Architecture

- **`mvp0_api` (`port 8000`)**: Serves the public authenticated endpoint `POST /api/v1/system/emergency-stop` (and `GET /api/v1/system/emergency-stop`, `POST /api/v1/system/emergency-stop/resume-requests*`) and writes the authoritative Kill Switch state (`state_key = 'KILL_SWITCH'`) to PostgreSQL.
- **`kill_switch` (`internal port 8001`)**: Independent internal watchdog container (`expose: ["8001"]`, no public host port, does not expose `/api/v1/system/emergency-stop`). Continuously reads Kill Switch state (`KILL_SWITCH`) and Risk Engine heartbeat (`RISK_ENGINE_HEARTBEAT`) from PostgreSQL and triggers automatic Kill Switch activation in PostgreSQL if the Risk Engine heartbeat is missing or stale (`> 60` seconds).

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
