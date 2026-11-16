from datetime import date


def request_dict(state: dict) -> dict:
    req = state.get("user_request") or {}
    return req if isinstance(req, dict) else {}


def trip_length_days(req: dict) -> int | None:
    start = req.get("start_date")
    end = req.get("end_date")
    if not start or not end:
        return None
    try:
        delta = date.fromisoformat(str(end)) - date.fromisoformat(str(start))
        return max(delta.days + 1, 1)
    except ValueError:
        return None


def extract_coords(destination_info: object) -> tuple[float, float] | None:
    if not isinstance(destination_info, dict):
        return None
    coords = destination_info.get("coordinates")
    if isinstance(coords, dict):
        lat, lon = coords.get("lat"), coords.get("lon")
        try:
            if lat is not None and lon is not None:
                return float(lat), float(lon)
        except (TypeError, ValueError):
            pass
    results = destination_info.get("nominatim_results")
    if isinstance(results, list) and results:
        first = results[0]
        if isinstance(first, dict):
            try:
                return float(first["lat"]), float(first["lon"])
            except (KeyError, TypeError, ValueError):
                return None
    return None
