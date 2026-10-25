"""Polish number formatting and chart colors shared by the app and the report."""

from src.features import MAX_HOURS_SINCE_PREV

# Brand blue and orange (validated as a pair), ink for the rules baseline, gray for context.
BLUE = "#1F5FBF"
ORANGE = "#EB6834"
INK = "#172033"
GRAY = "#B5B2A8"


def fmt_int(value: float) -> str:
    return f"{value:,.0f}".replace(",", " ")


def fmt_pln(value: float) -> str:
    return f"{fmt_int(value)} zł"


def fmt_pct(share: float, digits: int = 0) -> str:
    return f"{share * 100:.{digits}f}%".replace(".", ",")


def fmt_step(percent: float) -> str:
    """A slider threshold given in percent: 0.5 -> '0,5%', 10 -> '10%'."""
    return f"{percent:g}%".replace(".", ",")


def fmt_hours(hours: float) -> str:
    if hours >= MAX_HOURS_SINCE_PREV:
        return "ponad tydzień"
    if hours < 1:
        return f"{hours * 60:.0f} min"
    return f"{hours:.1f} h".replace(".", ",")
