from __future__ import annotations

from playwright.sync_api import Page

from tests_full_system.helpers.waits import wait_for_visible


class OfficePage:
    def __init__(self, page: Page) -> None:
        self.page = page

    def assert_core_actions_visible(self) -> None:
        for selector in [
            "#officeVatCalculateButton",
            "#officeMeasureModeLinear",
        ]:
            wait_for_visible(self.page, selector)

    def assert_sections_visible(self) -> None:
        for selector in [
            '[data-tab-panel="office"] .admin-bank-card',
            ".office-user-card",
            "#officeVatModeSwitch",
            "#officeMeasureModeSwitch",
        ]:
            wait_for_visible(self.page, selector)

    def assert_vat_calculator_surface(self) -> None:
        for selector in [
            "#officeVatModeSwitch",
            "#officeVatModeNet",
            "#officeVatModeGross",
            "#officeVatInputLabel",
            "#officeVatValue",
            "#officeVatCalculateButton",
            "#officeVatAmount",
            "#officeVatNetResult",
            "#officeVatGrossResult",
        ]:
            wait_for_visible(self.page, selector)

    def assert_measure_calculator_surface(self) -> None:
        for selector in [
            "#officeMeasureModeSwitch",
            "#officeMeasureModeLinear",
            "#officeMeasureModeArea",
            "#officeMeasurePrimaryLabel",
            "#officeMeasureValue",
            "#officeMeasureWidth",
            "#officeMeasureCalculateButton",
            "#officeMeasureWidthResult",
            "#officeMeasureLengthResult",
            "#officeMeasureAreaResult",
        ]:
            wait_for_visible(self.page, selector)
