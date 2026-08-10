from app import _manual_order_catalog_customer_row


def test_manual_order_catalog_customer_row_includes_first_time_customer():
    row = _manual_order_catalog_customer_row(
        {
            "customer_guid": "14f83123-0ebd-483c-8187-046277457074",
            "customer_id": "515358687",
            "customer_name": "פיבין חומרי בניין בע״מ",
            "active": "TRUE",
            "address": "קהילת ציון 27",
            "city": "עפולה",
            "country": "IL",
        }
    )

    assert row["customer_key"] == "guid:14f83123-0ebd-483c-8187-046277457074"
    assert row["customer_id"] == "515358687"
    assert row["customer_name"] == "פיבין חומרי בניין בע״מ"
    assert row["address_label"] == "קהילת ציון 27, עפולה, IL"
    assert row["documents_count"] == 0
    assert row["last_document_date"] == ""
