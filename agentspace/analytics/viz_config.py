"""
Configuration for visualization colors, themes, and styles.
"""
from typing import Dict, List, Tuple

# Team color schemes (primary, secondary, accent)
TEAM_COLORS: Dict[str, Dict[str, str]] = {
    # Premier League
    'Arsenal': {'primary': '#EF0107', 'secondary': '#023474', 'accent': '#FFFFFF'},
    'Liverpool': {'primary': '#C8102E', 'secondary': '#00B2A9', 'accent': '#F6EB61'},
    'Manchester City': {'primary': '#6CABDD', 'secondary': '#1C2C5B', 'accent': '#FFFFFF'},
    'Manchester United': {'primary': '#DA291C', 'secondary': '#FBE122', 'accent': '#000000'},
    'Chelsea': {'primary': '#034694', 'secondary': '#FFFFFF', 'accent': '#ED1C24'},
    'Tottenham': {'primary': '#132257', 'secondary': '#FFFFFF', 'accent': '#000000'},

    # La Liga
    'Barcelona': {'primary': '#A50044', 'secondary': '#004D98', 'accent': '#EDBB00'},
    'Real Madrid': {'primary': '#FEBE10', 'secondary': '#00529B', 'accent': '#FFFFFF'},
    'Atlético Madrid': {'primary': '#CB3524', 'secondary': '#FFFFFF', 'accent': '#1B3C84'},

    # Serie A
    'Juventus': {'primary': '#000000', 'secondary': '#FFFFFF', 'accent': '#D6A022'},
    'Inter': {'primary': '#010E80', 'secondary': '#000000', 'accent': '#FFFFFF'},
    'AC Milan': {'primary': '#FB090B', 'secondary': '#000000', 'accent': '#FFFFFF'},
    'Napoli': {'primary': '#1E6EC8', 'secondary': '#FFFFFF', 'accent': '#000000'},
    'Roma': {'primary': '#8B0304', 'secondary': '#F7BF31', 'accent': '#000000'},

    # Bundesliga
    'Bayern Munich': {'primary': '#DC052D', 'secondary': '#0066B2', 'accent': '#FFFFFF'},
    'Borussia Dortmund': {'primary': '#FDE100', 'secondary': '#000000', 'accent': '#FFFFFF'},

    # Ligue 1
    'Paris Saint-Germain': {'primary': '#004170', 'secondary': '#DA020E', 'accent': '#FFFFFF'},

    # Others
    'Atalanta': {'primary': '#1A2E6C', 'secondary': '#000000', 'accent': '#FFFFFF'},
    'Como': {'primary': '#1E3B96', 'secondary': '#FFFFFF', 'accent': '#000000'},
}

# Matplotlib colormaps for different visualization types
COLORMAPS = {
    # Heat-based
    'heat': 'YlOrRd',
    'fire': 'hot',
    'sunset': 'RdYlBu_r',

    # Cool colors
    'cool': 'Blues',
    'ocean': 'GnBu',
    'ice': 'PuBu',

    # Green/Forest
    'forest': 'Greens',
    'jungle': 'YlGn',

    # Purple/Magenta
    'purple': 'Purples',
    'magma': 'magma',

    # Multi-color
    'plasma': 'plasma',
    'viridis': 'viridis',
    'rainbow': 'turbo',

    # Specific for football
    'pitch_green': 'YlGn',
    'pressure': 'Reds',
    'possession': 'Blues',
}

# Style presets for different use cases
STYLES = {
    'minimal': {
        'linewidth': 1,
        'alpha': 0.8,
        'edgecolor': 'black',
        'fontsize': 10,
        'title_size': 14,
    },
    'bold': {
        'linewidth': 2.5,
        'alpha': 1.0,
        'edgecolor': 'white',
        'fontsize': 12,
        'title_size': 18,
    },
    'presentation': {
        'figsize': (16, 10),
        'dpi': 300,
        'linewidth': 2,
        'alpha': 0.9,
        'fontsize': 14,
        'title_size': 24,
    },
    'report': {
        'figsize': (12, 8),
        'dpi': 200,
        'linewidth': 1.5,
        'alpha': 0.85,
        'fontsize': 11,
        'title_size': 16,
    },
    'social': {
        'figsize': (10, 10),  # Square for Instagram/Twitter
        'dpi': 150,
        'linewidth': 2,
        'alpha': 0.9,
        'fontsize': 13,
        'title_size': 20,
    },
}

# Pitch styles
PITCH_STYLES = {
    'default': {
        'pitch_type': 'statsbomb',
        'pitch_color': '#22312b',
        'line_color': '#c7d5cc',
        'line_zorder': 2,
    },
    'light': {
        'pitch_type': 'statsbomb',
        'pitch_color': '#ffffff',
        'line_color': '#000000',
        'line_zorder': 2,
    },
    'dark': {
        'pitch_type': 'statsbomb',
        'pitch_color': '#1a1a1a',
        'line_color': '#ffffff',
        'line_zorder': 2,
    },
    'grass': {
        'pitch_type': 'statsbomb',
        'pitch_color': '#7db84d',
        'line_color': '#ffffff',
        'line_zorder': 2,
        'stripe': True,
    },
    'classic': {
        'pitch_type': 'statsbomb',
        'pitch_color': '#3d8f3d',
        'line_color': '#ffffff',
        'line_zorder': 2,
    },
}

# Radar chart templates for different position types
RADAR_TEMPLATES = {
    'goalkeeper': [
        'saves', 'goals_against', 'clean_sheets',
        'passes_completed', 'long_passes',
        'sweeper_clearances', 'distribution_accuracy'
    ],
    'defender': [
        'tackles', 'interceptions', 'clearances',
        'blocks', 'aerial_duels_won',
        'passes_completed', 'progressive_passes'
    ],
    'midfielder': [
        'passes_completed', 'progressive_passes', 'key_passes',
        'tackles', 'interceptions',
        'shots', 'dribbles_completed'
    ],
    'attacker': [
        'goals', 'shots', 'shots_on_target',
        'key_passes', 'dribbles_completed',
        'aerial_duels_won', 'touches_in_box'
    ],
    'winger': [
        'crosses', 'dribbles_completed', 'key_passes',
        'shots', 'successful_take_ons',
        'passes_into_final_third', 'touches_in_box'
    ],
}

# Pizza chart color schemes
PIZZA_COLORS = {
    'blue_gold': ['#1a78cf', '#ff9300'],
    'red_blue': ['#d70232', '#1a78cf'],
    'green_purple': ['#00d084', '#7f00ff'],
    'orange_teal': ['#ff6b35', '#00d5e4'],
    'classic': ['#ee8130', '#4687bf'],
}

# Shot outcome colors
SHOT_COLORS = {
    'Goal': '#00FF00',
    'Saved': '#FFA500',
    'Blocked': '#FF0000',
    'Off T': '#999999',
    'Wayward': '#666666',
    'Post': '#FFFF00',
}

# Body part colors for shot maps
BODY_PART_COLORS = {
    'Right Foot': '#4287f5',
    'Left Foot': '#f54242',
    'Head': '#42f554',
    'Other': '#999999',
}


def get_team_color(team_name: str, color_type: str = 'primary') -> str:
    """
    Get team color by name.

    Args:
        team_name: Name of the team
        color_type: 'primary', 'secondary', or 'accent'

    Returns:
        Hex color code
    """
    team_colors = TEAM_COLORS.get(team_name, {})
    return team_colors.get(color_type, '#1a78cf')  # Default blue


def get_colormap(name: str) -> str:
    """
    Get matplotlib colormap name.

    Args:
        name: Colormap name or alias

    Returns:
        Matplotlib colormap name
    """
    return COLORMAPS.get(name, name)  # Return name if not found (might be valid matplotlib name)


def get_style(name: str) -> Dict:
    """
    Get style configuration.

    Args:
        name: Style preset name

    Returns:
        Style configuration dict
    """
    return STYLES.get(name, STYLES['minimal']).copy()


def get_pitch_style(name: str) -> Dict:
    """
    Get pitch style configuration.

    Args:
        name: Pitch style name

    Returns:
        Pitch style configuration dict
    """
    return PITCH_STYLES.get(name, PITCH_STYLES['default']).copy()


def get_radar_template(position: str) -> List[str]:
    """
    Get radar metrics template for position.

    Args:
        position: Player position type

    Returns:
        List of metric names
    """
    position_lower = position.lower()
    for key in RADAR_TEMPLATES:
        if key in position_lower:
            return RADAR_TEMPLATES[key].copy()
    return RADAR_TEMPLATES['midfielder'].copy()  # Default


def create_gradient_cmap(color1: str, color2: str, name: str = 'custom') -> str:
    """
    Create a custom gradient colormap between two colors.

    Args:
        color1: Start color (hex)
        color2: End color (hex)
        name: Name for the colormap

    Returns:
        Colormap name
    """
    # This would require matplotlib.colors.LinearSegmentedColormap
    # For now, return a similar existing colormap
    # TODO: Implement custom gradient colormap creation
    return 'Blues'  # Placeholder
