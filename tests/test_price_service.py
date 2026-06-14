import sys
import json
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent))


def _patch_config(tmp_dir):
    import config
    config.PRICE_CACHE_FILE = Path(tmp_dir) / 'price_cache.json'
    config.PRICE_FALLBACK_FILE = Path(tmp_dir) / 'price_fallback.json'

    fallback = {
        'default_per_state': {
            '19': {'apartment': 700, 'house': 500},
            '10': {'apartment': 1500, 'house': 900},
        },
        'cities': {
            '540': {'apartment': 730, 'house': 520},
        },
        'rooms_multiplier': {
            '1': 1.10, '2': 1.00, '3': 0.95, '4': 0.92, '5': 0.90,
        },
    }
    config.PRICE_FALLBACK_FILE.write_text(json.dumps(fallback), encoding='utf-8')


def test_fallback_city_exact():
    with tempfile.TemporaryDirectory() as tmp:
        _patch_config(tmp)
        import importlib
        import services.price_service as ps
        importlib.reload(ps)

        with patch('services.domria_client.DomRiaClient.search_median_price', return_value=None):
            result = ps.get_base_price(19, 540, 'apartment', 2)

        assert result['source'] in ('cache', 'cache_stale', 'fallback', 'domria_live')
        assert result['price_per_m2'] > 0


def test_fallback_state_default():
    with tempfile.TemporaryDirectory() as tmp:
        _patch_config(tmp)
        import importlib
        import services.price_service as ps
        importlib.reload(ps)

        with patch('services.domria_client.DomRiaClient.search_median_price', return_value=None):
            result = ps.get_base_price(19, 9999, 'apartment', 2)

        assert result['price_per_m2'] == 700.0


def test_cache_write_and_read():
    with tempfile.TemporaryDirectory() as tmp:
        _patch_config(tmp)
        import importlib
        import services.price_service as ps
        importlib.reload(ps)

        mock_result = {'price_per_m2': 800.0, 'sample_size': 42}
        with patch('services.domria_client.DomRiaClient.search_median_price', return_value=mock_result):
            r1 = ps.get_base_price(19, 540, 'apartment', 2)

        assert r1['source'] == 'domria_live'
        assert r1['price_per_m2'] == 800.0

        with patch('services.domria_client.DomRiaClient.search_median_price', return_value=None):
            r2 = ps.get_base_price(19, 540, 'apartment', 2)

        assert r2['source'] == 'cache'
        assert r2['price_per_m2'] == 800.0


def test_rooms_multiplier():
    with tempfile.TemporaryDirectory() as tmp:
        _patch_config(tmp)
        import importlib
        import services.price_service as ps
        importlib.reload(ps)

        with patch('services.domria_client.DomRiaClient.search_median_price', return_value=None):
            r1 = ps.get_base_price(19, 9999, 'apartment', 1)
            r3 = ps.get_base_price(19, 9999, 'apartment', 3)

        assert r1['price_per_m2'] == round(700 * 1.10, 2)
        assert r3['price_per_m2'] == round(700 * 0.95, 2)
