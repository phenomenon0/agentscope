"""
Integration helpers exposing Agentspace capabilities to agent frameworks.
"""

__all__ = [
    "register_statsbomb_tools",
    "init_session_with_statsbomb_tools",
    "register_statsbomb_online_index_tools",
    "register_wyscout_tools",
    "register_statsbomb_viz_tools",
    "register_advanced_viz_tools",
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
    "plot_pizza_chart_tool",
    "register_offline_index_tools",
    "register_event_analysis_tools",
    "get_player_events_ranked_by_metric_tool",
    "get_player_event_sequences_tool",
    "compare_player_events_tool",
    "filter_events_by_context_tool",
]


_LAZY_IMPORTS = {
    "register_statsbomb_tools": ("agentspace.agent_tools.statsbomb", "register_statsbomb_tools"),
    "init_session_with_statsbomb_tools": ("agentspace.agent_tools.statsbomb", "init_session_with_statsbomb_tools"),
    "list_competition_players_tool": ("agentspace.agent_tools.statsbomb", "list_competition_players_tool"),
    "list_team_players_tool": ("agentspace.agent_tools.statsbomb", "list_team_players_tool"),
    "player_season_summary_tool": ("agentspace.agent_tools.statsbomb", "player_season_summary_tool"),
    "summarise_match_performance": ("agentspace.agent_tools.statsbomb", "summarise_match_performance"),
    "team_season_summary_tool": ("agentspace.agent_tools.statsbomb", "team_season_summary_tool"),
    "player_multi_season_summary_tool": ("agentspace.agent_tools.statsbomb", "player_multi_season_summary_tool"),
    "compare_player_season_summaries_tool": ("agentspace.agent_tools.statsbomb", "compare_player_season_summaries_tool"),
    "player_report_template_tool": ("agentspace.agent_tools.statsbomb", "player_report_template_tool"),
    "register_statsbomb_online_index_tools": ("agentspace.agent_tools.online_index", "register_statsbomb_online_index_tools"),
    "register_wyscout_tools": ("agentspace.agent_tools.wyscout", "register_wyscout_tools"),
    "register_statsbomb_viz_tools": ("agentspace.agent_tools.viz", "register_statsbomb_viz_tools"),
    "plot_match_shot_map_tool": ("agentspace.agent_tools.viz", "plot_match_shot_map_tool"),
    "plot_event_heatmap_tool": ("agentspace.agent_tools.viz", "plot_event_heatmap_tool"),
    "plot_pass_network_tool": ("agentspace.agent_tools.viz", "plot_pass_network_tool"),
    "register_advanced_viz_tools": ("agentspace.agent_tools.advanced_viz", "register_advanced_viz_tools"),
    "plot_pizza_chart_tool": ("agentspace.agent_tools.advanced_viz", "plot_pizza_chart_tool"),
    "register_offline_index_tools": ("agentspace.agent_tools.offline_sqlite", "register_offline_index_tools"),
    "register_event_analysis_tools": ("agentspace.agent_tools.event_analysis", "register_event_analysis_tools"),
    "get_player_events_ranked_by_metric_tool": ("agentspace.agent_tools.event_analysis", "get_player_events_ranked_by_metric_tool"),
    "get_player_event_sequences_tool": ("agentspace.agent_tools.event_analysis", "get_player_event_sequences_tool"),
    "compare_player_events_tool": ("agentspace.agent_tools.event_analysis", "compare_player_events_tool"),
    "filter_events_by_context_tool": ("agentspace.agent_tools.event_analysis", "filter_events_by_context_tool"),
}


def __getattr__(name):
    if name not in _LAZY_IMPORTS:
        raise AttributeError(f"module 'agentspace.agent_tools' has no attribute '{name}'")
    module_name, attr_name = _LAZY_IMPORTS[name]
    module = __import__(module_name, fromlist=[attr_name])
    value = getattr(module, attr_name)
    globals()[name] = value
    return value
