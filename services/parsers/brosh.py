from services.parsers.shared_portal import parse_portal_purchase_order


CUSTOMER_NAME = 'ברוש ניר עבודות הנדסה ובנין בע"מ'


def parse(text: str):
    return parse_portal_purchase_order(text, CUSTOMER_NAME)
