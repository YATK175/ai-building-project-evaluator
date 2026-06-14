import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from services.rules_engine import (
    floor_coefficient,
    year_coefficient,
    calculate_price,
    CONDITION_COEFFICIENTS,
    CONDITION_LABELS,
)


def test_condition_coefficients_all_scores():
    assert CONDITION_COEFFICIENTS[1] == 0.65
    assert CONDITION_COEFFICIENTS[2] == 0.80
    assert CONDITION_COEFFICIENTS[3] == 1.00
    assert CONDITION_COEFFICIENTS[4] == 1.18
    assert CONDITION_COEFFICIENTS[5] == 1.40


def test_condition_labels_exist():
    for score in range(1, 6):
        assert score in CONDITION_LABELS
        assert isinstance(CONDITION_LABELS[score], str)
        assert len(CONDITION_LABELS[score]) > 0


def test_floor_coefficient_first_floor():
    assert floor_coefficient(1, 9) == 0.93


def test_floor_coefficient_last_floor():
    assert floor_coefficient(9, 9) == 0.96


def test_floor_coefficient_top_floor_high_rise():
    assert floor_coefficient(16, 16) == 0.96


def test_floor_coefficient_mid_floor():
    assert floor_coefficient(5, 9) == 1.0


def test_floor_coefficient_low_floor_highrise():
    assert floor_coefficient(2, 20) == 1.02
    assert floor_coefficient(3, 20) == 1.02


def test_floor_coefficient_none():
    assert floor_coefficient(None, None) == 1.0
    assert floor_coefficient(3, None) == 1.0
    assert floor_coefficient(None, 9) == 1.0


def test_year_coefficient_old():
    assert year_coefficient(1950) == 0.85
    assert year_coefficient(1959) == 0.85


def test_year_coefficient_soviet():
    assert year_coefficient(1960) == 0.90
    assert year_coefficient(1989) == 0.90


def test_year_coefficient_postsoviet():
    assert year_coefficient(1990) == 1.00
    assert year_coefficient(2009) == 1.00


def test_year_coefficient_modern():
    assert year_coefficient(2010) == 1.10
    assert year_coefficient(2019) == 1.10


def test_year_coefficient_new():
    assert year_coefficient(2020) == 1.15
    assert year_coefficient(2025) == 1.15


def test_year_coefficient_none():
    assert year_coefficient(None) == 1.0


def test_calculate_price_basic():
    result = calculate_price(1000, 50, 3, None, None, None, 'apartment', 'user')
    assert result['final_price'] == 50000
    assert result['price_min'] == round(50000 * 0.85)
    assert result['price_max'] == round(50000 * 1.15)


def test_calculate_price_condition_multiplier():
    base = calculate_price(1000, 50, 3, None, None, None, 'apartment', 'user')
    premium = calculate_price(1000, 50, 5, None, None, None, 'apartment', 'user')
    assert premium['final_price'] > base['final_price']
    assert abs(premium['final_price'] - round(1000 * 50 * 1.40)) < 2


def test_calculate_price_year_impact():
    old = calculate_price(1000, 50, 3, None, None, 1950, 'apartment', 'user')
    new_ = calculate_price(1000, 50, 3, None, None, 2023, 'apartment', 'user')
    assert new_['final_price'] > old['final_price']


def test_calculate_price_estimated_area_wider_spread():
    r_user = calculate_price(1000, 50, 3, None, None, None, 'apartment', 'user')
    r_est = calculate_price(1000, 50, 3, None, None, None, 'apartment', 'estimated')
    user_spread = r_user['price_max'] - r_user['price_min']
    est_spread = r_est['price_max'] - r_est['price_min']
    assert est_spread > user_spread


def test_calculate_price_house_ignores_floor():
    apt = calculate_price(1000, 50, 3, 1, 9, None, 'apartment', 'user')
    house = calculate_price(1000, 50, 3, 1, 9, None, 'house', 'user')
    assert house['final_price'] > apt['final_price']


def test_coefficients_dict_returned():
    result = calculate_price(1000, 50, 3, 5, 9, 2000, 'apartment', 'user')
    coefs = result['coefficients']
    assert 'condition' in coefs
    assert 'floor' in coefs
    assert 'year' in coefs
    assert 'combined' in coefs
