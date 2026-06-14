import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from services.vision_service import aggregate_vision_results


def _photo(room_type, score, confidence=0.9, low=12, high=18, defects=None, features=None):
    return {
        'room_type': room_type,
        'condition_score': score,
        'confidence': confidence,
        'approximate_area_m2': {'low': low, 'high': high},
        'defects': defects or [],
        'features': features or [],
    }


def test_condition_is_median_of_scores():
    results = [
        _photo('kitchen', 3),
        _photo('bedroom', 4),
        _photo('living_room', 4),
    ]
    agg = aggregate_vision_results(results)
    assert agg['condition_score'] == 4


def test_low_confidence_filtered():
    results = [
        _photo('kitchen', 5, confidence=0.1),
        _photo('bedroom', 3, confidence=0.9),
    ]
    agg = aggregate_vision_results(results)
    assert agg['condition_score'] == 3


def test_all_low_confidence_returns_neutral():
    results = [
        _photo('kitchen', 5, confidence=0.1),
        _photo('bedroom', 1, confidence=0.2),
    ]
    agg = aggregate_vision_results(results)
    assert agg['condition_score'] == 3


def test_area_sums_unique_rooms():
    results = [
        _photo('kitchen', 3, low=10, high=14),
        _photo('bedroom', 3, low=14, high=18),
        _photo('bedroom', 3, low=14, high=18),  # дублікат — не рахуємо
    ]
    agg = aggregate_vision_results(results)
    expected = (10 + 14 + 14 + 18) / 2
    assert agg['estimated_area_midpoint'] == expected


def test_exterior_excluded_from_area():
    results = [
        _photo('kitchen', 3, low=10, high=14),
        _photo('exterior', 3, low=100, high=200),
    ]
    agg = aggregate_vision_results(results)
    assert agg['estimated_area_midpoint'] == (10 + 14) / 2


def test_defects_deduplicated():
    results = [
        _photo('kitchen', 2, defects=['тріщина', 'цвіль']),
        _photo('bedroom', 2, defects=['тріщина', 'старий паркет']),
    ]
    agg = aggregate_vision_results(results)
    assert len(agg['defects']) == 3
    assert 'тріщина' in agg['defects']


def test_features_deduplicated():
    results = [
        _photo('kitchen', 4, features=['нова плитка', 'євровікна']),
        _photo('bathroom', 4, features=['євровікна', 'новий кахель']),
    ]
    agg = aggregate_vision_results(results)
    assert len(agg['features']) == 3


def test_empty_input_returns_neutral():
    agg = aggregate_vision_results([])
    assert agg['condition_score'] == 3
    assert agg['estimated_area_midpoint'] is None
