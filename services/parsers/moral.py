from services.parsers.generic import parse_generic


CUSTOMER_NAME = "מורל טכנולוגיות"


def parse(text: str):
    customer_name, items, header = parse_generic(text)
    if not customer_name:
        customer_name = CUSTOMER_NAME
    return customer_name, items, header
