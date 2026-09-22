from voxpilot.services.vast_models import _instance_ref, build_offer_query, extract_mapped_port, normalize_offer


def test_offer_query_uses_gb_threshold_and_policy():
    query = build_offer_query(
        24,
        0.98,
        0.50,
        disk_gb=60,
        verified_only=True,
        min_direct_ports=1,
        min_inet_down_mbps=100,
    )
    assert "gpu_ram>=24" in query
    assert "dph_total<=0.5000" in query
    assert "disk_space>=60" in query
    assert "verified=true" in query
    assert "inet_down>=100" in query


def test_normalize_offer_converts_raw_vram_mb():
    offer = normalize_offer(
        {
            "id": 77,
            "gpu_name": "RTX 3090",
            "gpu_ram": 24576,
            "dph_total": 0.19,
            "reliability": 0.995,
            "inet_down": 800,
        }
    )
    assert offer.offer_id == 77
    assert 24 <= offer.gpu_ram_gb < 25
    assert offer.price_per_hour == 0.19


def test_extract_mapped_port_known_shape():
    raw = {"ports": {"8080/tcp": [{"HostPort": "42117"}]}}
    assert extract_mapped_port(raw, 8080) == 42117


def test_stopped_vast_container_is_not_reported_as_failed():
    ref = _instance_ref(
        {"id": 1, "actual_status": "exited", "intended_status": "stopped", "cur_state": "stopped"},
        api_port=8080,
    )
    assert ref.status == "stopped"

    failed = _instance_ref(
        {"id": 1, "actual_status": "exited", "intended_status": "running", "cur_state": "exited"},
        api_port=8080,
    )
    assert failed.status == "exited"


def test_exited_container_with_running_intent_is_still_starting():
    ref = _instance_ref(
        {"id": 1, "actual_status": "exited", "intended_status": "running", "cur_state": "running"},
        api_port=8080,
    )
    assert ref.status == "starting"
