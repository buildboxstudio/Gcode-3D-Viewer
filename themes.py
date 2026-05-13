"""
Theme definitions for GCode 3D Viewer.
"""

THEMES = {
    'dark': {
        'name': 'Dark',
        'bg': '#1e1e2e',
        'bg_alt': '#181825',
        'panel': '#313244',
        'surface': '#1a1a2e',
        'text': '#cdd6f4',
        'text_dim': '#a6adc8',
        'accent': '#89b4fa',
        'accent2': '#cba6f7',
        'success': '#a6e3a1',
        'warning': '#f9e2af',
        'error': '#f38ba8',
        'button_bg': '#45475a',
        'button_fg': '#cdd6f4',
        'select': '#45475a',
        'grid_color': (40, 40, 60),
        'viewport_bg': (26, 26, 46),
        'travel_color': (60, 60, 90),
        'placeholder_color': '#585b70',
    },
    'light': {
        'name': 'Light',
        'bg': '#eff1f5',
        'bg_alt': '#e6e9ef',
        'panel': '#dce0e8',
        'surface': '#ccd0da',
        'text': '#4c4f69',
        'text_dim': '#6c6f85',
        'accent': '#1e66f5',
        'accent2': '#8839ef',
        'success': '#40a02b',
        'warning': '#df8e1d',
        'error': '#d20f39',
        'button_bg': '#bcc0cc',
        'button_fg': '#4c4f69',
        'select': '#bcc0cc',
        'grid_color': (180, 185, 200),
        'viewport_bg': (204, 208, 218),
        'travel_color': (160, 165, 180),
        'placeholder_color': '#6c6f85',
    },
}


def get_theme(theme_name):
    """Get theme dict. Falls back to dark."""
    return THEMES.get(theme_name, THEMES['dark'])
