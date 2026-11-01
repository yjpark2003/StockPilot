"""Render the watchlist management screen."""
from pathlib import Path
from jinja2 import Environment, FileSystemLoader, select_autoescape
from server.theme import THEME_INIT_SCRIPT, THEME_TOGGLE_SCRIPT
from server.ui import navigation


def render_dashboard():
    environment = Environment(loader=FileSystemLoader(Path(__file__).parent / 'templates'),
                              autoescape=select_autoescape(['html']))
    return environment.get_template('stocks.html').render(
        navigation=navigation('stocks'), theme_init=THEME_INIT_SCRIPT,
        theme_script=THEME_TOGGLE_SCRIPT)
