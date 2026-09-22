import subprocess

import pytest

from voxpilot.services.audio_probe import ReferenceAudioError, ReferenceAudioTooLong, inspect_reference_file


def test_oversized_reference_is_rejected_by_decoded_duration(tmp_path, monkeypatch):
    sample = tmp_path / "reference.ogg"
    sample.write_bytes(b"OggS")
    monkeypatch.setattr(
        "voxpilot.services.audio_probe.subprocess.run",
        lambda *args, **kwargs: subprocess.CompletedProcess(args[0], 0, stdout='{"streams":[{"codec_type":"audio"}],"format":{"duration":"89.786500"}}', stderr=""),
    )

    with pytest.raises(ReferenceAudioTooLong) as caught:
        inspect_reference_file(sample)

    assert caught.value.duration_seconds == pytest.approx(89.7865)


def test_undecodable_reference_is_rejected_without_exposing_ffprobe_output(tmp_path, monkeypatch):
    sample = tmp_path / "reference.ogg"
    sample.write_bytes(b"not-audio")
    monkeypatch.setattr(
        "voxpilot.services.audio_probe.subprocess.run",
        lambda *args, **kwargs: subprocess.CompletedProcess(args[0], 1, stdout="", stderr="private file detail"),
    )

    with pytest.raises(ReferenceAudioError) as caught:
        inspect_reference_file(sample)

    assert "private file detail" not in str(caught.value)


def test_container_without_audio_stream_is_rejected(tmp_path, monkeypatch):
    sample = tmp_path / "reference.mp4"
    sample.write_bytes(b"video")
    monkeypatch.setattr(
        "voxpilot.services.audio_probe.subprocess.run",
        lambda *args, **kwargs: subprocess.CompletedProcess(args[0], 0, stdout='{"streams":[],"format":{"duration":"1.0"}}', stderr=""),
    )

    with pytest.raises(ReferenceAudioError):
        inspect_reference_file(sample)
