from __future__ import annotations

from playwright.sync_api import Page

from tests_full_system.helpers.waits import wait_for_visible


class AdminPage:
    def __init__(self, page: Page) -> None:
        self.page = page

    def assert_core_actions_visible(self) -> None:
        for selector in [
            "#supplierPackageMailButton",
            '[data-admin-business-doc-send="customer-onboarding-package"]',
            'a[href="/admin-drive/supplier-onboarding-package"]',
        ]:
            wait_for_visible(self.page, selector)

    def assert_sections_visible(self) -> None:
        for selector in [
            "#adminBankAccountsSection",
            "#adminTelecomSection",
            "#adminInsuranceSection",
            "#adminLoansSection",
            "#adminRealEstateSection",
            "#adminPropertiesSection",
            "#adminVehiclesSection",
            "#adminPazomatSection",
            "#adminSibusSection",
            "#adminDocsSection",
        ]:
            wait_for_visible(self.page, selector)

    def assert_jump_navigation_visible(self) -> None:
        for selector in [
            '[data-admin-target="adminBankAccountsSection"]',
            '[data-admin-target="adminTelecomSection"]',
            '[data-admin-target="adminInsuranceSection"]',
            '[data-admin-target="adminLoansSection"]',
            '[data-admin-target="adminRealEstateSection"]',
            '[data-admin-target="adminPropertiesSection"]',
            '[data-admin-target="adminVehiclesSection"]',
            '[data-admin-target="adminPazomatSection"]',
            '[data-admin-target="adminSibusSection"]',
            '[data-admin-target="adminDocsSection"]',
        ]:
            wait_for_visible(self.page, selector)

    def assert_docs_surface(self) -> None:
        for selector in [
            "#supplierPackageMailButton",
            '[data-admin-business-doc-send="business-tax-books"]',
            '[data-admin-business-doc-send="business-id-copy"]',
            '[href="/admin-drive/business-tax-books"]',
            '[href="/admin-drive/business-id-copy"]',
            '[href="/admin-drive/business-driver-license"]',
        ]:
            wait_for_visible(self.page, selector)

    def assert_finance_refresh_controls(self) -> None:
        for selector in [
            "[data-pazomat-refresh]",
            "[data-sibus-refresh]",
            '[href="/pazomat-drive-folder"]',
            '[href="/sibus-drive-folder"]',
            '[href="/insurance-drive-folder"]',
            '[href="/loans-drive-folder"]',
        ]:
            wait_for_visible(self.page, selector)

    def open_business_doc_send_modal_stub(self) -> None:
        self.page.evaluate(
            """
            () => {
              const modal = document.getElementById('adminBusinessDocSendModal');
              const meta = document.getElementById('adminBusinessDocSendMeta');
              if (!modal) return;
              if (meta) {
                meta.textContent = 'TEST | modal stub';
              }
              modal.classList.add('visible');
              modal.setAttribute('aria-hidden', 'false');
            }
            """
        )
        wait_for_visible(self.page, "#adminBusinessDocSendModal")

    def assert_business_doc_send_modal_surfaces(self) -> None:
        for selector in [
            "#adminBusinessDocSendClose",
            "#adminBusinessDocSendMeta",
            "#adminBusinessDocRecipients",
            "#adminBusinessDocPhone",
            "#adminBusinessDocSubject",
            "#adminBusinessDocEditor",
            "#adminBusinessDocAttachments",
            "#adminBusinessDocSendCancel",
            "#adminBusinessDocSendTest",
            "#adminBusinessDocSendWhatsapp",
            "#adminBusinessDocSendEmail",
        ]:
            wait_for_visible(self.page, selector)
