# tracks the IRS wash-sale rule: can't rebuy a ticker within 30 days of selling it at a loss
#
# simplifications (intentional, not oversights):
# - "same security" = identical ticker only, no "substantially identical" modeling
# - only the 30-days-AFTER window is enforced; pre-sale lookback would need forward knowledge
# - only loss sales are tracked (the sim only calls record_sale after a loss harvest)
#
# state: dict[ticker -> most recent sale date], latest sale wins if sold multiple times

import logging
from datetime import date, timedelta

logger = logging.getLogger(__name__)

WASH_SALE_WINDOW_DAYS = 30


def record_sale(restrictions: dict, ticker: str, sale_date: date) -> None:
    """Record a loss sale. Overwrites prior restriction for the same ticker."""
    restrictions[ticker] = sale_date
    logger.debug("Wash-sale restriction set: %s sold on %s", ticker, sale_date)


def is_blocked(restrictions: dict, ticker: str, purchase_date: date) -> bool:
    """True if buying ticker on purchase_date falls within a 30-day wash-sale window (inclusive)."""
    sale_date = restrictions.get(ticker)
    if sale_date is None:
        return False
    return sale_date <= purchase_date <= sale_date + timedelta(days=WASH_SALE_WINDOW_DAYS)


def get_eligible_replacements(
    restrictions: dict,
    candidates: list[str],
    purchase_date: date,
) -> list[str]:
    """Filter candidates to those not blocked on purchase_date. Order preserved."""
    return [t for t in candidates if not is_blocked(restrictions, t, purchase_date)]
