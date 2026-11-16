import pytest

from app.core.money import format_money, normalize_currency, parse_amount, parse_price


class TestNormalizeCurrency:
    def test_valid_code_uppercased(self):
        assert normalize_currency("inr") == "INR"

    def test_default_on_empty(self):
        assert normalize_currency(None) == "USD"
        assert normalize_currency("") == "USD"

    def test_default_on_invalid_length(self):
        assert normalize_currency("dollars") == "USD"

    def test_default_on_non_alpha(self):
        assert normalize_currency("1NR") == "USD"

    def test_custom_default(self):
        assert normalize_currency(None, default="EUR") == "EUR"


class TestParseAmount:
    def test_plain_number(self):
        assert parse_amount("123.45") == 123.45

    def test_thousands_separator(self):
        assert parse_amount("1,234.50") == 1234.50

    def test_invalid_returns_none(self):
        assert parse_amount("not a number") is None


class TestParsePrice:
    def test_numeric_input_assumes_usd(self):
        assert parse_price(130) == {"amount": 130.0, "currency": "USD"}

    def test_dollar_symbol(self):
        assert parse_price("from $130") == {"amount": 130.0, "currency": "USD"}

    def test_rupee_symbol(self):
        assert parse_price("Price: 9,073.69 INR") == {"amount": 9073.69, "currency": "INR"}

    def test_code_before_amount(self):
        result = parse_price("INR 9073.69")
        assert result == {"amount": 9073.69, "currency": "INR"}

    def test_amount_before_code(self):
        result = parse_price("9073.69 INR")
        assert result == {"amount": 9073.69, "currency": "INR"}

    def test_symbol_without_nearby_code_defaults_to_symbol_currency(self):
        result = parse_price("€50 per night")
        assert result == {"amount": 50.0, "currency": "EUR"}

    def test_none_when_no_amount(self):
        assert parse_price("no price mentioned here") is None

    def test_none_for_empty_string(self):
        assert parse_price("") is None

    def test_none_for_non_string_non_number(self):
        assert parse_price(None) is None
        assert parse_price({"amount": 5}) is None


class TestFormatMoney:
    def test_basic_formatting(self):
        assert format_money(1417764.15, "INR") == "1,417,764.15 INR"

    def test_small_amount(self):
        assert format_money(9.5, "USD") == "9.50 USD"

    @pytest.mark.parametrize("amount,currency,expected", [
        (0, "USD", "0.00 USD"),
        (-5.5, "EUR", "-5.50 EUR"),
    ])
    def test_edge_amounts(self, amount, currency, expected):
        assert format_money(amount, currency) == expected
