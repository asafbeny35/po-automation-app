from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo


BUSINESS_TIMEZONE = ZoneInfo("Asia/Jerusalem")


def business_today() -> date:
    """Return the document date according to the business' local timezone."""
    return datetime.now(BUSINESS_TIMEZONE).date()


def calculate_net_due_date(
    issue_date: date,
    payment_terms_value: str | int | float | None,
) -> date:
    """Calculate the app's "current month + N" payment date.

    The payment schedule used by the app starts at the first day of the month
    following the document date, adds the configured number of days, and then
    advances to the next first-of-month when the result is mid-month.
    """
    if isinstance(issue_date, datetime):
        issue_date = issue_date.date()
    if not isinstance(issue_date, date):
        raise TypeError("issue_date must be a date")

    try:
        terms_days = int(float(str(payment_terms_value or 0).strip() or 0))
    except (TypeError, ValueError):
        terms_days = 0
    terms_days = max(0, terms_days)

    if issue_date.month == 12:
        base_date = date(issue_date.year + 1, 1, 1)
    else:
        base_date = date(issue_date.year, issue_date.month + 1, 1)

    due_date = base_date + timedelta(days=terms_days)
    if due_date.day != 1:
        if due_date.month == 12:
            due_date = date(due_date.year + 1, 1, 1)
        else:
            due_date = date(due_date.year, due_date.month + 1, 1)
    return due_date
