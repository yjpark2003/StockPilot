"""Collection limits shared by the analyzer and isolated workers (seconds)."""
from pathlib import Path
import math
import yaml

DEFAULT_LIMITS = {
    'browser_setup': 15, 'navigation': 15, 'price': 25, 'news': 30,
    'financial': 30, 'short_interest': 30, 'benchmark': 20,
    'cleanup': 10, 'stock': 90, 'consecutive_timeouts': 3,
}


def load_limits():
    path = Path(__file__).resolve().parent.parent / 'config' / 'settings.yaml'
    config = yaml.safe_load(path.read_text(encoding='utf-8')) or {} if path.exists() else {}
    limits = {**DEFAULT_LIMITS, **config.get('collection_timeouts', {})}
    for key in DEFAULT_LIMITS:
        value = limits[key]
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
            raise ValueError(f'collection_timeouts.{key}는 양수여야 합니다.')
    if int(limits['consecutive_timeouts']) != limits['consecutive_timeouts']:
        raise ValueError('consecutive_timeouts는 양의 정수여야 합니다.')
    return limits
