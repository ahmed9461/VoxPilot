from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from voxpilot.db import Database

BILLING_KEYS = (
    "billing.started_at", "billing.active_since", "billing.active_seconds",
    "billing.price_per_hour", "billing.recovered_estimate",
)


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _parse_timestamp(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        stamp = datetime.fromisoformat(str(value))
    except (TypeError, ValueError):
        return None
    if stamp.tzinfo is None:
        stamp = stamp.replace(tzinfo=UTC)
    return stamp.astimezone(UTC)


def _snapshot(values: dict[str, Any], stamp: datetime) -> dict[str, Any] | None:
    price = values.get("billing.price_per_hour")
    started = _parse_timestamp(values.get("billing.started_at"))
    if price is None or started is None:
        return None
    seconds = float(values.get("billing.active_seconds") or 0.0)
    active = _parse_timestamp(values.get("billing.active_since"))
    if active is not None:
        seconds += max(0.0, (stamp - active).total_seconds())
    return {
        "started_at": started.isoformat(), "active": active is not None,
        "active_seconds": seconds,
        "elapsed_seconds": max(0.0, (stamp - started).total_seconds()),
        "price_per_hour": float(price),
        "estimated_cost_usd": seconds * float(price) / 3600.0,
        "measured_at": stamp.isoformat(),
        "recovered_estimate": bool(values.get("billing.recovered_estimate")),
    }


async def begin_billing(db: Database, price_per_hour: float, *, now: datetime | None = None, recovered: bool = False) -> None:
    stamp = (now or _utc_now()).astimezone(UTC)
    def begin(values):
        if values.get("billing.started_at"):
            return {}, None
        return {
            "billing.started_at": stamp.isoformat(),
            "billing.active_since": stamp.isoformat(),
            "billing.active_seconds": 0.0,
            "billing.price_per_hour": float(price_per_hour),
            "billing.recovered_estimate": recovered,
        }, None
    await db.transaction(BILLING_KEYS, begin)


async def pause_billing(db: Database, *, now: datetime | None = None) -> None:
    stamp = (now or _utc_now()).astimezone(UTC)
    def pause(values):
        snapshot = _snapshot(values, stamp)
        if snapshot is None or not snapshot["active"]:
            return {}, None
        return {"billing.active_seconds": snapshot["active_seconds"], "billing.active_since": None}, None
    await db.transaction(BILLING_KEYS, pause)


async def resume_billing(db: Database, *, now: datetime | None = None) -> None:
    stamp = (now or _utc_now()).astimezone(UTC)
    def resume(values):
        if not values.get("billing.started_at") or values.get("billing.active_since"):
            return {}, None
        return {"billing.active_since": stamp.isoformat()}, None
    await db.transaction(BILLING_KEYS, resume)


async def sync_billing_status(db: Database, status: str, *, now: datetime | None = None) -> None:
    normalized = str(status or "").lower()
    if normalized in {"running", "frozen"}:
        await resume_billing(db, now=now)
    elif normalized == "stopped":
        await pause_billing(db, now=now)


async def billing_snapshot(db: Database, *, now: datetime | None = None) -> dict[str, Any] | None:
    return _snapshot(await db.get_many(BILLING_KEYS), (now or _utc_now()).astimezone(UTC))


async def finalize_billing(db: Database, *, now: datetime | None = None) -> dict[str, Any] | None:
    stamp = (now or _utc_now()).astimezone(UTC)
    def finalize(values):
        snapshot = _snapshot(values, stamp)
        if snapshot is None:
            return {}, None
        snapshot["active"] = False
        updates = {key: None for key in BILLING_KEYS}
        updates["billing.last"] = snapshot
        return updates, snapshot
    return await db.transaction(BILLING_KEYS, finalize)


async def last_billing_snapshot(db: Database) -> dict[str, Any] | None:
    value = await db.get("billing.last")
    return value if isinstance(value, dict) else None
