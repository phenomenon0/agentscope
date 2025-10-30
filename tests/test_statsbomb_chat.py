from __future__ import annotations

from datetime import datetime, timezone

import pytest

from agentspace.agents import statsbomb_chat as chat


def test_system_prompt_includes_current_year_and_season(monkeypatch):
    target = datetime(2024, 10, 16, 12, 0, tzinfo=timezone.utc)

    class DummyDateTime:
        @classmethod
        def now(cls, tz=None):
            if tz is None:
                return target.replace(tzinfo=None)
            return target.astimezone(tz)

    monkeypatch.setattr(chat, "datetime", DummyDateTime)

    prompt = chat._system_prompt()
    assert "2024-10-16" in prompt
    assert "current year 2024" in prompt
    assert "2024/2025" in prompt


@pytest.mark.parametrize(
    ("month", "expected"),
    [
        (1, "2023/2024"),
        (6, "2023/2024"),
        (7, "2024/2025"),
        (12, "2024/2025"),
    ],
)
def test_season_label_for_today(month, expected):
    season = chat._season_label_for_today(datetime(2024, month, 1).date())
    assert season == expected
