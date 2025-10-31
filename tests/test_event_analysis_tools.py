"""
Tests for event analysis agent tools.
"""
import pytest
from agentspace.agent_tools.event_analysis import (
    get_player_events_ranked_by_metric_tool,
    get_player_event_sequences_tool,
    compare_player_events_tool,
    filter_events_by_context_tool,
    _extract_metric_value,
)


def test_extract_metric_value():
    """Test metric extraction from event dictionaries."""
    # Top-level field
    event = {"obv_for_after": 0.05, "minute": 45}
    assert _extract_metric_value(event, "obv_for_after") == 0.05

    # Nested field
    event = {"pass": {"length": 25.3}, "minute": 30}
    assert _extract_metric_value(event, "pass.length") == 25.3

    # Missing field
    event = {"minute": 10}
    assert _extract_metric_value(event, "obv_for_after") is None

    # Deeply nested
    event = {"shot": {"statsbomb_xg": 0.85}}
    assert _extract_metric_value(event, "shot.statsbomb_xg") == 0.85


@pytest.mark.integration
def test_get_player_events_ranked_by_metric():
    """Test ranking player events by metric."""
    # This is an integration test - requires real data
    # Mock/skip if no API access
    result = get_player_events_ranked_by_metric_tool(
        player_name="Bukayo Saka",
        event_type="Pass",
        metric_field="pass.length",  # Use pass.length as more reliable than OBV
        season_label="2024/2025",  # Use last season for stable data
        limit=5,
        match_limit=2,
    )

    # Should not error
    assert result is not None
    assert hasattr(result, 'content')
    assert hasattr(result, 'metadata')


@pytest.mark.integration
def test_filter_events_by_context():
    """Test filtering events by context."""
    result = filter_events_by_context_tool(
        player_name="Bukayo Saka",
        event_type="Pass",
        season_label="2024/2025",
        context_filters={
            "zone": "final_third",
            "minute_range": [0, 45],  # First half only
        },
        limit=10,
        match_limit=2,
    )

    assert result is not None
    assert hasattr(result, 'content')


@pytest.mark.integration
def test_compare_player_events():
    """Test comparing two players' events."""
    result = compare_player_events_tool(
        player1_name="Bukayo Saka",
        player2_name="Gabriel Martinelli",
        event_type="Pass",
        metric_field="pass.length",
        season_label="2024/2025",
        limit=5,
        match_limit=2,
    )

    assert result is not None
    assert hasattr(result, 'metadata')
    # Should have both players' data
    if 'player1_avg' in result.metadata:
        assert 'player2_avg' in result.metadata


def test_get_player_events_ranked_missing_player():
    """Test error handling for missing player."""
    result = get_player_events_ranked_by_metric_tool(
        player_name="NonExistent Player XYZ",
        event_type="Pass",
        metric_field="obv_for_after",
        season_label="2024/2025",
        limit=10,
    )

    # Should return error response
    assert result is not None
    assert "Could not find player" in result.content[0].text or "error" in result.metadata
