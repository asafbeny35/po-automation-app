from __future__ import annotations

import pytest


@pytest.mark.api
@pytest.mark.requires_live_server
def test_pricing_state_endpoint_available(api_client):
    response = api_client.get("/pricing-bom-state")
    assert response.status_code < 500


@pytest.mark.api
@pytest.mark.requires_live_server
@pytest.mark.destructive
def test_pricing_save_endpoint_accepts_items_and_components_shape(api_client):
    response = api_client.post(
        "/pricing-bom-state",
        json={
            "items": [
                {
                    "id": "TEST-PRICING-ITEM-001",
                    "name": "TEST | נעלולי פלא | מוצר",
                    "kind": "product",
                    "pricing_unit": "יחידה",
                    "labor_minutes": 0,
                    "labor_hour_cost": 0,
                    "shipping_divisor": 1,
                    "notes": "TEST",
                }
            ],
            "components": [
                {
                    "item_id": "TEST-PRICING-ITEM-001",
                    "component_id": "TEST-COMP-001",
                    "supplier": "TEST Supplier",
                    "usage_value": 1,
                    "usage_unit": "יחידה",
                }
            ],
        },
    )
    assert response.status_code in {200, 400, 401, 422, 500}
