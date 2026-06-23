from __future__ import annotations

from playwright.sync_api import Page

from tests_full_system.helpers.waits import wait_for_visible


class PricingPage:
    def __init__(self, page: Page) -> None:
        self.page = page

    def assert_core_actions_visible(self) -> None:
        for selector in [
            "#pricingBomAddProductButton",
            "#pricingBomAddServiceButton",
            "#pricingBomLoadButton",
            "#pricingBomSaveButton",
        ]:
            wait_for_visible(self.page, selector)

    def assert_pricing_surface(self) -> None:
        for selector in [
            "#pricingBomSummary",
            "#pricingBomAddProductSidebarButton",
            "#pricingBomAddServiceSidebarButton",
            "#pricingBomFilterSwitch",
            "#pricingBomItemsList",
            "#pricingBomEditorEmpty",
        ]:
            wait_for_visible(self.page, selector)
        for selector in [
            "#pricingBomProgress",
            "#pricingBomProgressFill",
            "#pricingBomProgressTitle",
            "#pricingBomProgressPercent",
        ]:
            assert self.page.locator(selector).count() >= 1

    def open_editor_stub(self) -> None:
        self.page.evaluate(
            """
            () => {
              const empty = document.getElementById('pricingBomEditorEmpty');
              const content = document.getElementById('pricingBomEditorContent');
              const title = document.getElementById('pricingBomEditorTitle');
              if (empty) empty.hidden = true;
              if (content) content.hidden = false;
              if (title && !title.textContent.trim()) title.textContent = 'TEST | נעלולי פלא | פריט תמחור';
            }
            """
        )
        wait_for_visible(self.page, "#pricingBomEditorContent")

    def assert_editor_surface(self) -> None:
        for selector in [
            "#pricingBomEditorContent",
            "#pricingBomEditorTitle",
            "#pricingBomItemName",
            "#pricingBomItemKind",
            "#pricingBomPricingUnit",
            "#pricingBomLaborMinutes",
            "#pricingBomLaborHourCost",
            "#pricingBomShippingTotal",
            "#pricingBomShippingDivisor",
            "#pricingBomNotes",
            "#pricingBomAddDimensionButton",
            "#pricingBomMaterialsCost",
            "#pricingBomLaborCost",
            "#pricingBomShippingUnitCost",
            "#pricingBomTotalCost",
            "#pricingBomAddComponentBottomButton",
        ]:
            wait_for_visible(self.page, selector)
        for selector in [
            "#pricingBomDimensionsHost",
            "#pricingBomComponentsTableBody",
        ]:
            assert self.page.locator(selector).count() >= 1
