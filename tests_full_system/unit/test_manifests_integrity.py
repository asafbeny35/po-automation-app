from __future__ import annotations

from tests_full_system.manifests.flows import CRITICAL_END_TO_END_FLOWS
from tests_full_system.manifests.mobile import MOBILE_DOMAINS, MOBILE_SAFE_ENDPOINTS
from tests_full_system.manifests.routes import ROUTE_MANIFEST
from tests_full_system.manifests.tabs import TOP_LEVEL_TABS


def test_top_level_tabs_have_unique_ids():
    ids = [item["tab_id"] for item in TOP_LEVEL_TABS]
    assert len(ids) == len(set(ids))


def test_route_manifest_has_unique_method_path_pairs():
    pairs = [(item["method"], item["path"]) for item in ROUTE_MANIFEST]
    assert len(pairs) == len(set(pairs))


def test_critical_flows_have_unique_ids():
    ids = [item["id"] for item in CRITICAL_END_TO_END_FLOWS]
    assert len(ids) == len(set(ids))


def test_route_manifest_categories_are_present():
    assert {item["category"] for item in ROUTE_MANIFEST}


def test_mobile_domains_have_unique_ids():
    assert len(MOBILE_DOMAINS) == len(set(MOBILE_DOMAINS))


def test_mobile_safe_endpoints_have_unique_values():
    assert len(MOBILE_SAFE_ENDPOINTS) == len(set(MOBILE_SAFE_ENDPOINTS))
