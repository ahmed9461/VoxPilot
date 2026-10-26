from __future__ import annotations

import json
import math
import re
from typing import Any

from voxpilot.domain import GpuOffer, InstanceRef


def build_offer_query(
    min_gpu_ram_gb: int,
    min_reliability: float,
    max_price_usd_hour: float,
    *,
    disk_gb: int = 60,
    verified_only: bool = True,
    datacenter_only: bool = False,
    min_direct_ports: int = 1,
    min_inet_down_mbps: float = 0,
    min_inet_up_mbps: float = 0,
) -> str:
    terms = [
        "num_gpus=1",
        "rentable=true",
        "rented=false",
        f"gpu_ram>={int(min_gpu_ram_gb)}",
        f"reliability>={min_reliability:.4f}",
        f"dph_total<={max_price_usd_hour:.4f}",
        f"disk_space>={int(disk_gb)}",
    ]
    if verified_only:
        terms.append("verified=true")
    if datacenter_only:
        terms.append("datacenter=true")
    if min_direct_ports > 0:
        terms.append(f"direct_port_count>={int(min_direct_ports)}")
    if min_inet_down_mbps > 0:
        terms.append(f"inet_down>={float(min_inet_down_mbps):.0f}")
    if min_inet_up_mbps > 0:
        terms.append(f"inet_up>={float(min_inet_up_mbps):.0f}")
    return " ".join(terms)


def _num(raw: dict[str, Any], *names: str, default: float = 0.0) -> float:
    for name in names:
        value = raw.get(name)
        if value is not None:
            try:
                number = float(value)
                if math.isfinite(number):
                    return number
            except (TypeError, ValueError):
                pass
    return default


def _optional_num(raw: dict[str, Any], *names: str) -> float | None:
    if all(raw.get(name) is None for name in names):
        return None
    # A supplied invalid/zero measurement is not an omitted measurement.
    return _num(raw, *names, default=0.0)


def normalize_offer(raw: dict[str, Any]) -> GpuOffer:
    gpu_ram_mb = _num(raw, "gpu_ram", "gpu_ram_mb")
    reliability = _optional_num(raw, "reliability", "reliability2")
    if reliability is not None and reliability > 1:
        reliability /= 100
    verified_raw = raw.get("verified", raw.get("verification"))
    verified = None if verified_raw is None else str(verified_raw).lower() in {"verified", "true", "1"}
    return GpuOffer(
        offer_id=int(_num(raw, "id", "ask_id")),
        gpu_name=str(raw.get("gpu_name") or raw.get("gpu_display_name") or "Unknown GPU"),
        gpu_ram_gb=gpu_ram_mb / 1000 if gpu_ram_mb else _num(raw, "gpu_ram_gb"),
        price_per_hour=(_num(raw, "dph_total") if raw.get("dph_total") is not None
                        else _num(raw, "dph_base", "price")),
        reliability=reliability,
        dlperf=_optional_num(raw, "dlperf"),
        location=raw.get("geolocation") or raw.get("location"),
        inet_down_mbps=_optional_num(raw, "inet_down"),
        inet_up_mbps=_optional_num(raw, "inet_up"),
        disk_bw_mbps=_optional_num(raw, "disk_bw"),
        inet_down_cost_per_gb=_optional_num(raw, "inet_down_cost"),
        inet_up_cost_per_gb=_optional_num(raw, "inet_up_cost"),
        disk_space_gb=_optional_num(raw, "disk_space"),
        verified=verified,
        raw=raw,
    )


def network_rank(offer: GpuOffer, preferred_mbps: float = 1000.0) -> tuple:
    """Advertised speed tiers first, then price; never an actual speed test."""
    down = offer.inet_down_mbps or 0.0
    target = max(1.0, preferred_mbps)
    tier = sum(down >= threshold for threshold in (target / 2, target, target * 2, target * 5))
    return (-tier, offer.price_per_hour, -down, -(offer.inet_up_mbps or 0),
            -(offer.disk_bw_mbps or 0), -(offer.dlperf or 0), offer.offer_id)


def _coerce_mapping(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, list) and value and isinstance(value[0], dict):
        return value[0]
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            if isinstance(parsed, dict):
                return parsed
            if isinstance(parsed, list) and parsed and isinstance(parsed[0], dict):
                return parsed[0]
        except json.JSONDecodeError:
            match = re.search(r"new_contract[^0-9]+([0-9]+)", value)
            if match:
                return {"new_contract": int(match.group(1))}
    return {}


def _extract_rows(value: Any, *keys: str) -> list[dict[str, Any]]:
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError:
            return []
    if isinstance(value, list):
        return [item for item in value if isinstance(item, dict)]
    if isinstance(value, dict):
        for key in keys:
            nested = value.get(key)
            if isinstance(nested, list):
                return [item for item in nested if isinstance(item, dict)]
            if isinstance(nested, dict):
                return [nested]
    return []


def _merge_nonempty(primary: dict[str, Any], fallback: dict[str, Any]) -> dict[str, Any]:
    merged = dict(fallback)
    for key, value in primary.items():
        if value not in (None, "", [], {}):
            merged[key] = value
    return merged


def extract_mapped_port(raw: dict[str, Any], internal_port: int) -> int | None:
    candidates = [raw]
    for nested_key in ("instance", "instances"):
        nested = raw.get(nested_key)
        if isinstance(nested, dict):
            candidates.append(nested)
        elif isinstance(nested, list):
            candidates.extend(item for item in nested if isinstance(item, dict))
    key = f"{internal_port}/tcp"
    for source in candidates:
        ports = source.get("ports")
        if isinstance(ports, dict):
            mappings = ports.get(key) or ports.get(str(internal_port))
            if isinstance(mappings, list) and mappings:
                item = mappings[0]
                if isinstance(item, dict):
                    value = item.get("HostPort") or item.get("host_port")
                    if value:
                        return int(value)
            elif isinstance(mappings, dict):
                value = mappings.get("HostPort") or mappings.get("host_port")
                if value:
                    return int(value)
        value = source.get(f"VAST_TCP_PORT_{internal_port}") or source.get(f"vast_tcp_port_{internal_port}")
        if value:
            return int(value)
    return None


def _instance_ref(raw: dict[str, Any], *, api_port: int, fallback_id: int = 0) -> InstanceRef:
    actual = str(raw.get("actual_status") or "").lower()
    intended = str(raw.get("intended_status") or "").lower()
    current = str(raw.get("cur_state") or "").lower()
    # Vast reports a successfully stopped container as actual=exited while
    # intended/cur_state are stopped. It is not a failed instance.
    if actual == "exited" and intended == "stopped" and current == "stopped":
        status = "stopped"
    elif actual == "exited" and intended == "running" and current == "running":
        status = "starting"
    else:
        status = str(
            raw.get("actual_status")
            or raw.get("intended_status")
            or raw.get("status")
            or raw.get("cur_state")
            or raw.get("state")
            or "unknown"
        )
    public_ip = raw.get("public_ipaddr") or raw.get("public_ip") or raw.get("ssh_host")
    instance_id = int(raw.get("id") or raw.get("instance_id") or fallback_id or 0)
    return InstanceRef(
        instance_id=instance_id,
        status=status,
        public_ip=str(public_ip) if public_ip else None,
        mapped_port=extract_mapped_port(raw, api_port),
        raw=raw,
    )
