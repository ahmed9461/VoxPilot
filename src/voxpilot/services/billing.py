from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from voxpilot.db import Database


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


async def begin_billing(db: Database, price_per_hour: float, *, now: datetime | None = None) -> None:
    stamp = (now or _utc_now()).astimezone(UTC)
    await db.set_many(
        {
            "billing.started_at": stamp.isoformat(),
            "billing.active_since": stamp.isoformat(),
            "billing.active_seconds": 0.0,
            "billing.price_per_hour": float(price_per_hour),
        }
    )


async def pause_billing(db: Database, *, now: datetime | None = None) -> None:
    stamp = (now or _utc_now()).astimezone(UTC)
    active_since = _parse_timestamp(await db.get("billing.active_since"))
    if active_since is None:
        return
    accumulated = float(await db.get("billing.active_seconds", 0.0) or 0.0)
    accumulated += max(0.0, (stamp - active_since).total_seconds())
    await db.set_many({"billing.active_seconds": accumulated, "billing.active_since": None})


async def resume_billing(db: Database, *, now: datetime | None = None) -> None:
    if await db.get("billing.active_since"):
        return
    stamp = (now or _utc_now()).astimezone(UTC)
    await db.set("billing.active_since", stamp.isoformat())


async def sync_billing_status(db: Database, status: str, *, now: datetime | None = None) -> None:
    normalized = str(status or "").lower()
    if normalized in {"running", "frozen"}:
        await resume_billing(db, now=now)
    elif normalized == "stopped":
        await pause_billing(db, now=now)


async def billing_snapshot(db: Database, *, now: datetime | None = None) -> dict[str, Any] | None:
    price = await db.get("billing.price_per_hour")
    started_at = _parse_timestamp(await db.get("billing.started_at"))
    if price is None or started_at is None:
        return None
    stamp = (now or _utc_now()).astimezone(UTC)
    active_seconds = float(await db.get("billing.active_seconds", 0.0) or 0.0)
    active_since = _parse_timestamp(await db.get("billing.active_since"))
    if active_since is not None:
        active_seconds += max(0.0, (stamp - active_since).total_seconds())
    price_per_hour = float(price)
    return {
        "started_at": started_at.isoformat(),
        "active": active_since is not None,
        "active_seconds": active_seconds,
        "elapsed_seconds": max(0.0, (stamp - started_at).total_seconds()),
        "price_per_hour": price_per_hour,
        "estimated_cost_usd": active_seconds * price_per_hour / 3600.0,
        "measured_at": stamp.isoformat(),
    }


async def finalize_billing(db: Database, *, now: datetime | None = None) -> dict[str, Any] | None:
    stamp = (now or _utc_now()).astimezone(UTC)
    await pause_billing(db, now=stamp)
    snapshot = await billing_snapshot(db, now=stamp)
    if snapshot is not None:
        await db.set("billing.last", snapshot)
    await db.set_many(
        {
            "billing.started_at": None,
            "billing.active_since": None,
            "billing.active_seconds": None,
            "billing.price_per_hour": None,
        }
    )
    return snapshot


async def last_billing_snapshot(db: Database) -> dict[str, Any] | None:
    value = await db.get("billing.last")
    return value if isinstance(value, dict) else None
