def geocode_key(query: str) -> str:
    return f"travel:cache:geocode:{' '.join(query.casefold().split())}"


def fx_key(base_currency: str) -> str:
    return f"travel:cache:fx:{base_currency.upper()}"


def media_key(query: str) -> str:
    return f"travel:cache:media:{' '.join(query.casefold().split())}"


def trip_lock_key(trip_id: str) -> str:
    return f"travel:lock:trip:{trip_id}"
