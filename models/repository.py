import json
from datetime import datetime
from models.database import get_connection


def save_evaluation(browser_id: str, evaluation: dict, input_data: dict, photo_ids: list) -> int:
    conn = get_connection()
    try:
        cur = conn.execute(
            """
            INSERT INTO evaluations (
                created_at, browser_id,
                state_id, state_name, city_id, city_name,
                realty_type, rooms_count, floor, total_floors, year_built,
                user_area, user_description,
                final_area, area_source,
                condition_score, condition_label,
                base_price_per_m2, price_source,
                final_price, price_min, price_max,
                coefficients_json, factors_json, explanation, mode
            ) VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
            )
            """,
            (
                datetime.now().strftime('%Y-%m-%dT%H:%M:%S'),
                browser_id,
                input_data.get('state_id'),
                input_data.get('state_name', ''),
                input_data.get('city_id'),
                input_data.get('city_name', ''),
                input_data.get('realty_type'),
                input_data.get('rooms_count'),
                input_data.get('floor'),
                input_data.get('total_floors'),
                input_data.get('year_built'),
                input_data.get('user_area'),
                input_data.get('user_description', ''),
                evaluation['final_area'],
                evaluation['area_source'],
                evaluation['condition_score'],
                evaluation['condition_label'],
                evaluation['base_price_per_m2'],
                evaluation['price_source'],
                evaluation['final_price'],
                evaluation['price_min'],
                evaluation['price_max'],
                json.dumps(evaluation.get('coefficients', {}), ensure_ascii=False),
                json.dumps(evaluation.get('factors', []), ensure_ascii=False),
                evaluation.get('explanation', ''),
                evaluation.get('mode', 'full'),
            ),
        )
        eval_id = cur.lastrowid

        for idx, filename in enumerate(photo_ids):
            conn.execute(
                'INSERT INTO evaluation_photos (evaluation_id, filename, order_index) VALUES (?, ?, ?)',
                (eval_id, filename, idx),
            )
        conn.commit()
        return eval_id
    finally:
        conn.close()


def get_history(browser_id: str) -> list:
    conn = get_connection()
    try:
        rows = conn.execute(
            """
            SELECT e.id, e.created_at, e.city_name, e.state_name,
                   e.realty_type, e.rooms_count, e.final_price, e.condition_label,
                   (SELECT filename FROM evaluation_photos
                    WHERE evaluation_id = e.id ORDER BY order_index LIMIT 1) AS thumbnail
            FROM evaluations e
            WHERE e.browser_id = ?
            ORDER BY e.created_at DESC
            """,
            (browser_id,),
        ).fetchall()
        result = []
        for row in rows:
            item = dict(row)
            if item['thumbnail']:
                item['thumbnail'] = f"/uploads/{item['thumbnail']}"
            result.append(item)
        return result
    finally:
        conn.close()


def get_evaluation(eval_id: int, browser_id: str) -> dict | None:
    conn = get_connection()
    try:
        row = conn.execute(
            'SELECT * FROM evaluations WHERE id = ? AND browser_id = ?',
            (eval_id, browser_id),
        ).fetchone()
        if row is None:
            return None
        data = dict(row)
        data['coefficients'] = json.loads(data.pop('coefficients_json', '{}'))
        data['factors'] = json.loads(data.pop('factors_json', '[]'))
        photos = conn.execute(
            'SELECT filename, order_index, detected_room FROM evaluation_photos WHERE evaluation_id = ? ORDER BY order_index',
            (eval_id,),
        ).fetchall()
        data['photos'] = [dict(p) for p in photos]
        return data
    finally:
        conn.close()


def delete_evaluation(eval_id: int, browser_id: str) -> list[str]:
    conn = get_connection()
    try:
        row = conn.execute(
            'SELECT id FROM evaluations WHERE id = ? AND browser_id = ?',
            (eval_id, browser_id),
        ).fetchone()
        if row is None:
            return []
        filenames = [
            r['filename']
            for r in conn.execute(
                'SELECT filename FROM evaluation_photos WHERE evaluation_id = ?',
                (eval_id,),
            ).fetchall()
        ]
        conn.execute('DELETE FROM evaluations WHERE id = ?', (eval_id,))
        conn.commit()
        return filenames
    finally:
        conn.close()
