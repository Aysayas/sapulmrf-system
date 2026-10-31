import re

NUMBER = re.compile(r"-?\d[\d,.]*")


def safe_cell(value):
    """Excel runs a text cell starting with these as a formula, and operators can type names and recipients."""
    if isinstance(value, str) and value[:1] in ("=", "+", "-", "@", "\t", "\r") and not NUMBER.fullmatch(value):
        return "'" + value
    return value


def safe_row(row) -> list:
    return [safe_cell(v) for v in row]
