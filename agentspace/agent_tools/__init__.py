"""
Integration helpers exposing Agentspace capabilities to agent frameworks.
"""

from .statsbomb import (
    compare_player_season_summaries_tool,
    init_session_with_statsbomb_tools,
    list_competition_players_tool,
    list_team_players_tool,
    player_multi_season_summary_tool,
    player_season_summary_tool,
    summarise_match_performance,
    register_statsbomb_tools,
    team_season_summary_tool,
    player_report_template_tool,
)
from .online_index import (
    register_statsbomb_online_index_tools,
)
from .wyscout import (
    register_wyscout_tools,
)
from .viz import (
    register_statsbomb_viz_tools,
    plot_match_shot_map_tool,
    plot_event_heatmap_tool,
    plot_pass_network_tool,
)
from .offline_sqlite import (
    register_offline_index_tools,
)

__all__ = [
    "register_statsbomb_tools",
    "init_session_with_statsbomb_tools",
    "register_statsbomb_online_index_tools",
    "register_wyscout_tools",
    "register_statsbomb_viz_tools",
    "list_competition_players_tool",
    "list_team_players_tool",
    "player_season_summary_tool",
    "summarise_match_performance",
    "team_season_summary_tool",
    "player_multi_season_summary_tool",
    "compare_player_season_summaries_tool",
    "player_report_template_tool",
    "plot_match_shot_map_tool",
    "plot_event_heatmap_tool",
    "plot_pass_network_tool",
    "register_offline_index_tools",
]
