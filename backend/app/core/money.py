from __future__ import annotations

import re
from typing import Any

SYMBOLS = {
    "$": "USD",
    "€": "EUR",
    "£": "GBP",
    "¥": "JPY",
    "₹": "INR",
}

CODE_RE = re.compile(r"\b(USD|EUR|GBP|INR|JPY|AUD|CAD|CHF|SGD|AED|NZD)\b", re.I)
# The thousands-grouped branch requires at least one ",ddd" group (note the
# trailing "+", not "*"): otherwise a plain 4+ digit number with no commas
# (e.g. "9073.69") would match the grouped branch's leading \d{1,3} and stop
# after 3 digits, since regex alternation takes the first successful match
# rather than the longest one.
_AMOUNT = r"\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?"
AMOUNT_RE = re.compile(
    rf"(?P<sym>[$€£¥₹])\s*(?P<amount>{_AMOUNT})"
    rf"|(?P<amount2>{_AMOUNT})\s*(?P<code>USD|EUR|GBP|INR|JPY|AUD|CAD|CHF|SGD|AED|NZD)"
    rf"|(?P<code2>USD|EUR|GBP|INR|JPY|AUD|CAD|CHF|SGD|AED|NZD)\s*(?P<amount3>{_AMOUNT})",
    re.I,
)


def normalize_currency(value: object, default: str = "USD") -> str:
    text = str(value or default).strip().upper()
    if len(text) != 3 or not text.isalpha():
        return default
    return text


def parse_amount(raw: str) -> float | None:
    try:
        return float(raw.replace(",", ""))
    except ValueError:
        return None


def parse_price(text: object) -> dict[str, Any] | None:
    if isinstance(text, (int, float)):
        return {"amount": float(text), "currency": "USD"}
    if not isinstance(text, str) or not text.strip():
        return None
    match = AMOUNT_RE.search(text)
    if not match:
        return None
    g = match.groupdict()
    amount_s = g.get("amount") or g.get("amount2") or g.get("amount3")
    if not amount_s:
        return None
    amount = parse_amount(amount_s)
    if amount is None:
        return None
    code = (g.get("code") or g.get("code2") or "").upper()
    if not code and g.get("sym"):
        code = SYMBOLS.get(g["sym"], "USD")
    if not code:
        nearby = CODE_RE.search(text)
        code = nearby.group(1).upper() if nearby else "USD"
    return {"amount": amount, "currency": code}


def format_money(amount: float, currency: str) -> str:
    return f"{amount:,.2f} {currency}"
