"""Unit tests for the storage_health_check mission.

These tests are pure-mock — no real FlipperClient, no real Flipper. They
verify report shape, warnings logic, and summary rendering. Hardware
integration belongs in a separate live-device test suite.

Run with:
    pytest tests/missions/test_storage_health_check.py -v
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from missions.llmdr.missions.storage_health_check import (
    EXT_FREE_PCT_WARN,
    INT_FREE_PCT_WARN,
    StorageHealthReport,
    run,
)


def _make_client(
    int_info: dict | None,
    ext_info: dict | None,
    int_dirs: list[dict] | None = None,
    ext_dirs: list[dict] | None = None,
) -> MagicMock:
    """Build a mock client matching the FlipperClient surface `run()` uses.

    Pass `None` for an `*_info` to simulate that volume being unreadable
    (e.g. SD card absent). Pass `[]` for dirs to simulate an empty
    directory.
    """
    client = MagicMock()
    client.rpc = AsyncMock()
    client.storage = AsyncMock()

    async def storage_info(path: str) -> dict | None:
        if path == "/int":
            return int_info
        if path == "/ext":
            return ext_info
        return None

    async def list_detailed(path: str) -> list[dict]:
        if path == "/int":
            return int_dirs or []
        if path == "/ext":
            return ext_dirs or []
        return []

    client.rpc.storage_info.side_effect = storage_info
    client.storage.list_detailed.side_effect = list_detailed
    return client


class TestReportShape:
    """The report has the documented fields with correct types."""

    async def test_healthy_flipper_returns_full_report(self) -> None:
        client = _make_client(
            int_info={"total_space": 1_000_000, "free_space": 500_000},
            ext_info={"total_space": 32_000_000_000, "free_space": 16_000_000_000},
            int_dirs=[
                {"name": "apps", "type": "DIR", "size": 0},
                {"name": "system", "type": "DIR", "size": 0},
                {"name": "manifest.txt", "type": "FILE", "size": 1024},
            ],
            ext_dirs=[
                {"name": "nfc", "type": "DIR", "size": 0},
                {"name": "subghz", "type": "DIR", "size": 0},
                {"name": "apps_data", "type": "DIR", "size": 0},
            ],
        )

        report = await run(client)

        assert isinstance(report, StorageHealthReport)
        assert report.int_total == 1_000_000
        assert report.int_free == 500_000
        assert report.int_used_pct == pytest.approx(50.0)
        assert report.ext_total == 32_000_000_000
        assert report.ext_free == 16_000_000_000
        assert report.ext_used_pct == pytest.approx(50.0)
        assert report.ext_present is True
        # Top-level dirs are returned sorted, with FILE entries filtered out.
        assert report.int_top_dirs == ["apps", "system"]
        assert report.ext_top_dirs == ["apps_data", "nfc", "subghz"]
        assert report.warnings == []
        assert report.elapsed_ms >= 0

    async def test_sd_card_absent_marks_ext_present_false(self) -> None:
        client = _make_client(
            int_info={"total_space": 1_000_000, "free_space": 800_000},
            ext_info=None,
        )

        report = await run(client)

        assert report.ext_present is False
        assert report.ext_total == 0
        assert report.ext_free == 0
        assert report.ext_used_pct == 0.0
        # No warning for absent SD — that's a valid configuration.
        assert not any("/ext" in w for w in report.warnings)
        # And we don't even ask for /ext's top dirs.
        assert report.ext_top_dirs == []


class TestWarningsLogic:
    """Warnings fire only when thresholds are crossed."""

    async def test_ext_below_10_percent_free_triggers_warning(self) -> None:
        # 5% free → below the 10% threshold.
        client = _make_client(
            int_info={"total_space": 1_000_000, "free_space": 500_000},
            ext_info={"total_space": 1_000_000_000, "free_space": 50_000_000},
        )

        report = await run(client)

        assert any("/ext" in w and "5.0%" in w for w in report.warnings), (
            f"Expected /ext low-free warning, got: {report.warnings}"
        )

    async def test_ext_at_50_percent_free_no_warning(self) -> None:
        client = _make_client(
            int_info={"total_space": 1_000_000, "free_space": 500_000},
            ext_info={"total_space": 1_000_000_000, "free_space": 500_000_000},
        )

        report = await run(client)

        assert not any("/ext" in w for w in report.warnings)

    async def test_int_below_5_percent_free_triggers_warning(self) -> None:
        # 2% free → below the 5% threshold.
        client = _make_client(
            int_info={"total_space": 1_000_000, "free_space": 20_000},
            ext_info={"total_space": 1_000_000_000, "free_space": 500_000_000},
        )

        report = await run(client)

        assert any("/int" in w and "2.0%" in w for w in report.warnings), (
            f"Expected /int low-free warning, got: {report.warnings}"
        )

    async def test_int_unreadable_emits_warning(self) -> None:
        client = _make_client(
            int_info=None,
            ext_info={"total_space": 1_000_000_000, "free_space": 500_000_000},
        )

        report = await run(client)

        assert any("/int" in w and "no data" in w for w in report.warnings), (
            f"Expected /int no-data warning, got: {report.warnings}"
        )

    async def test_thresholds_match_module_constants(self) -> None:
        # Pin the contract: if someone changes the threshold, this test
        # forces them to also update the cookbook + this docstring.
        assert EXT_FREE_PCT_WARN == 10.0
        assert INT_FREE_PCT_WARN == 5.0


class TestSummary:
    """`summary()` produces a non-empty human-readable line."""

    async def test_summary_is_non_empty_string_for_healthy_flipper(self) -> None:
        client = _make_client(
            int_info={"total_space": 1_000_000, "free_space": 800_000},
            ext_info={"total_space": 32_000_000_000, "free_space": 16_000_000_000},
        )

        report = await run(client)
        text = report.summary()

        assert isinstance(text, str)
        assert text.strip() != ""
        assert "/int" in text
        assert "/ext" in text
        assert "No warnings." in text

    async def test_summary_mentions_absent_sd_card(self) -> None:
        client = _make_client(
            int_info={"total_space": 1_000_000, "free_space": 800_000},
            ext_info=None,
        )

        report = await run(client)
        text = report.summary()

        assert "SD card not present" in text

    async def test_summary_surfaces_warnings_when_present(self) -> None:
        client = _make_client(
            int_info={"total_space": 1_000_000, "free_space": 800_000},
            ext_info={"total_space": 1_000_000_000, "free_space": 50_000_000},
        )

        report = await run(client)
        text = report.summary()

        assert "Warnings:" in text
        assert "/ext" in text
