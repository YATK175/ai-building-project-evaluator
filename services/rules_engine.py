CONDITION_COEFFICIENTS = {
    1: 0.65,
    2: 0.80,
    3: 1.00,
    4: 1.18,
    5: 1.40,
}

CONDITION_LABELS = {
    1: 'Потребує капремонту',
    2: 'Незадовільний стан',
    3: 'Житловий стан',
    4: 'Євроремонт',
    5: 'Преміум',
}


def floor_coefficient(floor: int | None, total_floors: int | None) -> float:
    if floor is None or total_floors is None:
        return 1.0
    if floor == 1:
        return 0.93
    if floor == total_floors:
        return 0.96
    if 2 <= floor <= 3 and total_floors > 9:
        return 1.02
    return 1.0


def year_coefficient(year_built: int | None) -> float:
    if year_built is None:
        return 1.0
    if year_built < 1960:
        return 0.85
    if year_built < 1990:
        return 0.90
    if year_built < 2010:
        return 1.00
    if year_built < 2020:
        return 1.10
    return 1.15


def calculate_price(
    base_price_per_m2: float,
    area: float,
    condition_score: int,
    floor: int | None,
    total_floors: int | None,
    year_built: int | None,
    realty_type: str,
    area_source: str,
) -> dict:
    coef_condition = CONDITION_COEFFICIENTS.get(condition_score, 1.0)
    coef_floor = floor_coefficient(floor, total_floors) if realty_type == 'apartment' else 1.0
    coef_year = year_coefficient(year_built)

    combined = coef_condition * coef_floor * coef_year
    final_price = round(base_price_per_m2 * area * combined)

    spread = 0.20 if area_source == 'estimated' else 0.15
    price_min = round(final_price * (1 - spread))
    price_max = round(final_price * (1 + spread))

    return {
        'final_price': final_price,
        'price_min': price_min,
        'price_max': price_max,
        'coefficients': {
            'condition': coef_condition,
            'floor': coef_floor,
            'year': coef_year,
            'combined': round(combined, 3),
        },
    }
