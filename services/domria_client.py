import statistics
import logging
import httpx
from config import DOMRIA_API_KEY, DOMRIA_BASE_URL

logger = logging.getLogger(__name__)

_REALTY_CATEGORY = {'apartment': 1, 'house': 4}


class DomRiaClient:
    def __init__(self):
        self._key = DOMRIA_API_KEY

    def _get(self, path: str, params: dict, timeout: float = 15.0):
        params['api_key'] = self._key
        params['lang_id'] = 4
        resp = httpx.get(f'{DOMRIA_BASE_URL}{path}', params=params, timeout=timeout)
        resp.raise_for_status()
        return resp.json()

    def fetch_all_regions(self) -> list:
        if not self._key:
            return []
        try:
            states = self._get('/dom/states', {})
            regions = []
            for state in states:
                state_id = state.get('stateID') or state.get('state_id') or state.get('id')
                name = state.get('name', '')
                if not state_id:
                    continue
                try:
                    cities_raw = self._get(f'/dom/cities/{state_id}', {})
                    cities = [
                        {
                            'city_id': c.get('cityID') or c.get('city_id') or c.get('id'),
                            'name': c.get('name', ''),
                        }
                        for c in cities_raw
                        if (c.get('cityID') or c.get('city_id') or c.get('id'))
                    ]
                except Exception:
                    cities = []
                regions.append({'state_id': state_id, 'name': name, 'cities': cities})
            return regions
        except Exception as exc:
            logger.error('fetch_all_regions: %s', exc)
            return []

    def search_median_price(
        self,
        state_id: int,
        city_id: int,
        realty_type: str,
        rooms_count: int,
    ) -> dict | None:
        if not self._key:
            return None
        category = _REALTY_CATEGORY.get(realty_type, 1)
        params = {
            'category': category,
            'realty_type': 2,
            'operation_type': 1,
            'state_id': state_id,
            'city_id': city_id,
            'page': 0,
            'per_page': 100,
        }
        if rooms_count and rooms_count <= 5:
            params['characteristic[209][from]'] = rooms_count
            params['characteristic[209][to]'] = rooms_count

        try:
            data = self._get('/dom/search', params)
            items = data.get('items', [])
            if not items:
                return None
            price_per_m2, sample = _calculate_median_price_per_m2(items)
            if price_per_m2 is None:
                return None
            return {'price_per_m2': price_per_m2, 'sample_size': sample}
        except Exception as exc:
            logger.error('search_median_price: %s', exc)
            return None

    def is_available(self, timeout: float = 3.0) -> bool:
        if not self._key:
            return False
        try:
            resp = httpx.get(
                f'{DOMRIA_BASE_URL}/dom/states',
                params={'api_key': self._key, 'lang_id': 4},
                timeout=timeout,
            )
            return resp.status_code < 500
        except Exception:
            return False


def _calculate_median_price_per_m2(items: list) -> tuple:
    prices = []
    for item in items:
        usd = item.get('priceArr', {}).get('USD') or item.get('price_USD')
        area = (
            item.get('total_square_meters')
            or item.get('totalSquareMeters')
            or item.get('living_square_meters')
            or item.get('livingSquareMeters')
        )
        if not usd or not area:
            continue
        try:
            usd = float(usd)
            area = float(area)
        except (TypeError, ValueError):
            continue
        if area < 10:
            continue
        ppm2 = usd / area
        if 100 < ppm2 < 5000:
            prices.append(ppm2)

    if not prices:
        return None, 0
    return round(statistics.median(prices), 2), len(prices)
