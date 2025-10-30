# Advanced Visualization Library Plan

## Overview

Expand the visualization capabilities with professional mplsoccer charts for player analysis, tactical breakdowns, and match reporting.

## New Visualization Types

### 1. Player Radar Charts
**Purpose:** Multi-dimensional player performance analysis
**Features:**
- Customizable metrics (passing, defending, attacking, etc.)
- Compare multiple players
- Season/match aggregates
- Color themes (team colors, custom)
- Different radar shapes (circular, polygon)

**Example Use Cases:**
- Scouting reports
- Player comparisons
- Season performance reviews

**Parameters:**
- `player_name` or `player_id`
- `metrics`: List of stat categories
- `comparison_player` (optional)
- `color_scheme`: 'default', 'team', 'custom'
- `season_id`, `competition_id`

### 2. Pizza Charts (Comparison Charts)
**Purpose:** Colorful percentile-based player comparisons
**Features:**
- Percentile rankings across metrics
- Visual comparison slices
- Team color themes
- Position-specific metrics
- League/competition benchmarking

**Example Use Cases:**
- Player vs. player comparisons
- Position analysis
- Transfer targets evaluation

**Parameters:**
- `player_name`
- `comparison_player` (optional)
- `metrics`: List of stat categories
- `colors`: List of colors for slices
- `benchmark`: 'league', 'position', 'top5'

### 3. KDE Action Zones (Heatmaps with Density)
**Purpose:** Show player activity with smooth density estimation
**Features:**
- Kernel density estimation for actions
- Multiple action types (passes, shots, tackles)
- Custom colormaps
- Overlay on pitch
- Zone annotations

**Example Use Cases:**
- Where a player operates
- Action concentration analysis
- Tactical positioning

**Parameters:**
- `player_name` or `team_name`
- `action_types`: ['pass', 'shot', 'tackle', etc.]
- `colormap`: 'Blues', 'Reds', 'Greens', etc.
- `levels`: Density contour levels
- `match_id` or aggregated

### 4. Shot Freeze Frames
**Purpose:** Visualize shot scenarios with player positions
**Features:**
- Show shooter, goalkeeper, defenders
- Expected goals (xG) overlay
- Pressure visualization
- Shot outcome
- Defensive line visualization

**Example Use Cases:**
- Shot analysis
- Defensive organization
- Goal-scoring opportunities

**Parameters:**
- `match_id`
- `shot_id` or `event_id`
- `show_xg`: Boolean
- `show_pressure`: Boolean
- `colors`: Dict of player types

### 5. Enhanced Shot Maps
**Purpose:** Improved shot visualizations with more context
**Features:**
- xG values per shot
- Shot outcome colors
- Player labels
- Body part indicators
- Distance/angle analysis

**Example Use Cases:**
- Shooting analysis
- Finishing quality
- Shot selection

**Parameters:**
- `player_name` or `team_name`
- `match_id` or aggregated
- `show_xg`: Boolean
- `color_by`: 'outcome', 'xg', 'body_part'
- `size_by`: 'xg', 'uniform'

### 6. Formation Plots (Barcelona Style)
**Purpose:** Show team shape with player positions
**Features:**
- Starting XI positions
- Formation overlays (4-3-3, 4-4-2, etc.)
- Player names/numbers
- Average positions
- Movement arrows (optional)

**Example Use Cases:**
- Pre-match lineups
- Tactical setup
- Position analysis

**Parameters:**
- `match_id`
- `team_name`
- `formation`: '433', '442', etc.
- `show_names`: Boolean
- `show_numbers`: Boolean
- `style`: 'barca', 'minimal', 'detailed'

### 7. Pass Reception Formations (with KDE)
**Purpose:** Show where players receive passes in their formation
**Features:**
- Formation layout with mini-pitches
- KDE heatmaps per position
- Player names
- Reception counts
- Customizable grid layout

**Example Use Cases:**
- Build-up play analysis
- Player positioning
- Tactical patterns

**Parameters:**
- `match_id`
- `team_name`
- `formation`: '433', '442', etc.
- `colormap`: 'Blues', 'Reds', etc.
- `show_counts`: Boolean

## Architecture

### Module Structure

```
agentspace/
├── analytics/
│   ├── mplsoccer_viz.py          # Existing (heatmaps, pass networks, shot maps)
│   ├── radar_charts.py            # NEW: Player radars
│   ├── pizza_charts.py            # NEW: Pizza/comparison charts
│   ├── action_zones.py            # NEW: KDE density plots
│   ├── shot_analysis.py           # NEW: Freeze frames, enhanced shots
│   ├── formation_plots.py         # NEW: Formation visualizations
│   └── viz_config.py              # NEW: Colors, themes, styles
│
├── agent_tools/
│   ├── viz.py                     # Existing tools
│   └── advanced_viz.py            # NEW: Tools for all new viz types
│
└── services/
    └── viz_data_prep.py           # NEW: Data preparation for visualizations
```

### Customization System

**Color Themes:**
```python
TEAM_COLORS = {
    'Arsenal': {'primary': '#EF0107', 'secondary': '#023474'},
    'Liverpool': {'primary': '#C8102E', 'secondary': '#00B2A9'},
    'Manchester City': {'primary': '#6CABDD', 'secondary': '#1C2C5B'},
    # ... more teams
}

COLORMAPS = {
    'heat': 'YlOrRd',
    'cool': 'Blues',
    'forest': 'Greens',
    'sunset': 'RdYlBu_r',
    'plasma': 'plasma',
    'viridis': 'viridis'
}
```

**Style Presets:**
```python
STYLES = {
    'minimal': {
        'linewidth': 1,
        'alpha': 0.8,
        'edgecolor': 'black'
    },
    'bold': {
        'linewidth': 2,
        'alpha': 1.0,
        'edgecolor': 'white'
    },
    'presentation': {
        'figsize': (16, 10),
        'dpi': 300,
        'title_size': 20
    }
}
```

## Data Requirements

### Player Stats for Radars/Pizzas
- Need aggregated season stats
- Per 90 minute metrics
- Percentile rankings
- Position-specific benchmarks

**Action Items:**
- Create stat aggregation functions
- Build percentile calculation system
- Add position filtering

### Shot Event Data
- Shot coordinates (x, y)
- xG values
- Body part, outcome
- Freeze frame data (player positions)

**Action Items:**
- Parse freeze_frame from events
- Calculate xG if not provided
- Extract player positions from 360 data

### Formation Data
- Starting XI with positions
- Average positions if available
- Player names, numbers
- Formation string (e.g., "4-3-3")

**Action Items:**
- Parse lineup data
- Calculate average positions from events
- Infer formation from positions

## Implementation Phases

### Phase 1: Foundation (Week 1)
- [x] Set up module structure
- [ ] Create color/theme configuration
- [ ] Build data preparation utilities
- [ ] Add basic radar chart
- [ ] Add basic pizza chart

### Phase 2: Action Analysis (Week 1-2)
- [ ] Implement KDE action zones
- [ ] Enhanced shot maps with xG
- [ ] Shot freeze frames
- [ ] Add customization options

### Phase 3: Formation & Tactics (Week 2)
- [ ] Formation plot module
- [ ] Pass reception formations
- [ ] Movement/arrow overlays
- [ ] Tactical annotations

### Phase 4: Polish & Integration (Week 2-3)
- [ ] Agent tools for all viz types
- [ ] Testing suite
- [ ] Documentation
- [ ] Example gallery

## Agent Tool Interface

### Example Tool Signatures

```python
def plot_player_radar_tool(
    player_name: str,
    metrics: List[str],
    match_id: Optional[int] = None,
    season_id: Optional[int] = None,
    comparison_player: Optional[str] = None,
    color_scheme: str = "default",
    output_dir: Optional[str] = None,
) -> ToolResponse:
    """Generate a player radar chart."""
    pass

def plot_pizza_chart_tool(
    player_name: str,
    comparison_player: Optional[str] = None,
    metrics: Optional[List[str]] = None,
    colors: Optional[List[str]] = None,
    benchmark: str = "league",
    output_dir: Optional[str] = None,
) -> ToolResponse:
    """Generate a pizza comparison chart."""
    pass

def plot_action_zones_tool(
    player_name: Optional[str] = None,
    team_name: Optional[str] = None,
    match_id: Optional[int] = None,
    action_types: List[str] = ["pass", "shot"],
    colormap: str = "Blues",
    levels: int = 100,
    output_dir: Optional[str] = None,
) -> ToolResponse:
    """Generate KDE action zone visualization."""
    pass
```

## Testing Strategy

1. **Unit Tests**: Each viz function with mock data
2. **Integration Tests**: Full flow with real StatsBomb data
3. **Visual Tests**: Save reference images, compare outputs
4. **Agent Tests**: Test tool calls through agent

## Success Criteria

- [ ] All 7 visualization types implemented
- [ ] Customization working (colors, themes, styles)
- [ ] Agent can call all tools successfully
- [ ] Images render correctly in chat UI
- [ ] Documentation complete
- [ ] Tests passing

## Future Enhancements

- Interactive visualizations (Plotly)
- Animated sequence plots
- Video frame overlays
- Custom metric definitions
- Export to PDF reports
- Template system for quick reports

## Resources

- mplsoccer docs: https://mplsoccer.readthedocs.io/
- StatsBomb open data: https://github.com/statsbomb/open-data
- Color schemes: https://colorbrewer2.org/
- Football icons: https://www.flaticon.com/
