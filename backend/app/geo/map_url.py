from urllib.parse import quote


def map_url(lat: float | str, lon: float | str, zoom: int = 15) -> str:
    """Public OpenStreetMap URL for a coordinate. URL only — no embed HTML."""
    lat_f = float(lat)
    lon_f = float(lon)
    return (
        f"https://www.openstreetmap.org/?mlat={lat_f}&mlon={lon_f}"
        f"#map={zoom}/{lat_f}/{lon_f}"
    )


def map_search_url(query: str) -> str:
    """Public OSM search URL when coordinates are unknown."""
    return f"https://www.openstreetmap.org/search?query={quote(query)}"
