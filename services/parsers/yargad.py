from services.parsers.shared_portal import parse_portal_purchase_order


CUSTOMER_NAME = 'ירגד פרויקטים בע"מ'


def parse(text: str):
    return parse_portal_purchase_order(text, CUSTOMER_NAME)
