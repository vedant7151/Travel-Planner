import asyncio
from typing import Any

from app.agents.common import extract_coords, request_dict
from app.core.money import format_money, normalize_currency, parse_price
from app.geo.map_url import map_search_url, map_url
from app.tools.fx import convert_amount
from app.tools.media import place_image_url


def _user_currency(req: dict) -> str:
    return normalize_currency(req.get("currency"), "USD")


async def priced_in_user_currency(
    source_text: object,
    user_currency: str,
    *,
    stated: object = None,
) -> dict[str, Any] | None:
    parsed = parse_price(stated) if stated not in (None, "") else None
    if parsed is None:
        parsed = parse_price(source_text)
    if parsed is None:
        return None
    converted = await convert_amount(parsed["amount"], parsed["currency"], user_currency)
    if converted is None:
        return {
            "amount": parsed["amount"],
            "currency": parsed["currency"],
            "display": format_money(parsed["amount"], parsed["currency"]),
            "note": f"Could not convert {parsed['currency']} to {user_currency}",
        }
    return {
        "amount": converted,
        "currency": user_currency,
        "display": format_money(converted, user_currency),
        "source_amount": parsed["amount"],
        "source_currency": parsed["currency"],
    }


def location_map_url(dest: dict | None, fallback_query: str | None = None) -> str | None:
    coords = extract_coords(dest) if dest else None
    if coords:
        return map_url(coords[0], coords[1])
    if fallback_query:
        return map_search_url(fallback_query)
    return None


async def enrich_destination_payload(payload: dict, destination_name: str) -> dict:
    results = payload.get("nominatim_results")
    rows: list[dict[str, Any]] = []
    if isinstance(results, list):
        for row in results[:6]:
            if isinstance(row, dict):
                rows.append(dict(row))
    queries = [destination_name]
    for row in rows:
        short = str(row.get("display_name") or row.get("name") or destination_name).split(",")[0]
        if short not in queries:
            queries.append(short)
    queries = queries[:4]
    images = await asyncio.gather(*[place_image_url(q) for q in queries])
    image_by_query = dict(zip(queries, images))
    dest_image = image_by_query.get(destination_name)

    places: list[dict[str, Any]] = []
    if rows:
        enriched_results = []
        for row in rows:
            name = row.get("display_name") or row.get("name") or destination_name
            short = str(name).split(",")[0]
            try:
                url = map_url(row["lat"], row["lon"])
            except (KeyError, TypeError, ValueError):
                url = map_search_url(str(name))
            image = image_by_query.get(short) or dest_image
            row["map_url"] = url
            row["image_url"] = image
            enriched_results.append(row)
            places.append({"name": name, "map_url": url, "image_url": image})
        payload["nominatim_results"] = enriched_results
    if not payload.get("map_url"):
        payload["map_url"] = location_map_url(payload, destination_name)
    payload["image_url"] = dest_image or (places[0].get("image_url") if places else None)
    payload["places"] = places or [
        {
            "name": destination_name,
            "map_url": payload.get("map_url") or map_search_url(destination_name),
            "image_url": payload.get("image_url"),
        }
    ]
    return payload


async def enrich_listing(item: dict, user_currency: str, dest_map: str | None, dest_image: str | None) -> dict:
    row = dict(item)
    snippet = " ".join(
        str(part)
        for part in (row.get("title"), row.get("snippet") or row.get("body") or row.get("text"))
        if part
    )
    price = await priced_in_user_currency(
        snippet,
        user_currency,
        stated=row.get("stated_price_or_null") or row.get("price"),
    )
    if price:
        row["price"] = price
        row["stated_price_or_null"] = price["display"]
    if dest_map:
        row["map_url"] = dest_map
    if dest_image and not row.get("image_url"):
        row["image_url"] = dest_image
    return row


async def enrich_itinerary(itinerary: dict, dest: dict | None, destination_name: str) -> dict:
    payload = dict(itinerary)
    dest_map = location_map_url(dest, destination_name)
    dest_image = dest.get("image_url") if isinstance(dest, dict) else None
    places = dest.get("places") if isinstance(dest, dict) else None
    days = payload.get("days")
    if isinstance(days, list):
        new_days = []
        for i, day in enumerate(days):
            if not isinstance(day, dict):
                new_days.append(day)
                continue
            entry = dict(day)
            place = None
            if isinstance(places, list) and places:
                place = places[min(i, len(places) - 1)]
            entry["map_url"] = (place or {}).get("map_url") or dest_map
            entry["image_url"] = (place or {}).get("image_url") or dest_image
            new_days.append(entry)
        payload["days"] = new_days
    legs = payload.get("travel_legs")
    if isinstance(legs, list):
        new_legs = []
        for leg in legs:
            if not isinstance(leg, dict):
                new_legs.append(leg)
                continue
            entry = dict(leg)
            if dest_map:
                entry["map_url"] = dest_map
            new_legs.append(entry)
        payload["travel_legs"] = new_legs
    payload["map_url"] = dest_map
    payload["image_url"] = dest_image
    return payload


async def user_budget(req: dict) -> dict[str, Any]:
    currency = _user_currency(req)
    usd = req.get("budget_usd")
    try:
        usd_f = float(usd)
    except (TypeError, ValueError):
        return {"currency": currency, "amount": None, "display": None, "budget_usd": usd}
    converted = await convert_amount(usd_f, "USD", currency)
    amount = converted if converted is not None else usd_f
    ccy = currency if converted is not None else "USD"
    return {
        "budget_usd": usd_f,
        "amount": amount,
        "currency": ccy,
        "display": format_money(amount, ccy),
    }


async def finalize_plan_media_and_prices(state: dict, structured: dict) -> dict:
    req = request_dict(state)
    dest = state.get("destination_info") if isinstance(state.get("destination_info"), dict) else {}
    currency = _user_currency(req)
    destination_name = str(req.get("destination") or "")
    dest_map = dest.get("map_url") or location_map_url(dest, destination_name)
    dest_image = dest.get("image_url")
    places = dest.get("places") if isinstance(dest.get("places"), list) else []
    public_places = [
        {
            "name": p.get("name"),
            "map_url": p.get("map_url"),
            "image_url": p.get("image_url"),
        }
        for p in places
        if isinstance(p, dict)
    ]

    itinerary = structured.get("itinerary")
    if isinstance(itinerary, dict):
        structured["itinerary"] = await enrich_itinerary(itinerary, dest, destination_name)

    for key in ("accommodation", "transport"):
        rows = structured.get(key)
        if isinstance(rows, list):
            structured[key] = [
                await enrich_listing(row, currency, dest_map, dest_image)
                if isinstance(row, dict)
                else row
                for row in rows
            ]

    structured["currency"] = currency
    structured["budget"] = await user_budget(req)
    structured["map_url"] = dest_map
    structured["image_url"] = dest_image
    structured["places"] = public_places
    return structured
