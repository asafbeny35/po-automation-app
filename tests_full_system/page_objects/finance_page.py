from __future__ import annotations

from playwright.sync_api import Page

from tests_full_system.helpers.waits import wait_for_idle_ui, wait_for_visible


class FinancePage:
    def __init__(self, page: Page) -> None:
        self.page = page

    def assert_core_actions_visible(self) -> None:
        for selector in [
            "#financeInvoicesLoadButton",
            "#financeInvoicesSendButton",
            "#financeInvoicesDriveFolderButton",
            "#financeInvoicesExportPdfButton",
            "#financeInvoicesExportButton",
            "#financeInvoicesCollapseButton",
            "#financeInvoicesAddButton",
        ]:
            wait_for_visible(self.page, selector)
        assert self.page.locator("#financeInvoicesFileInput").count() >= 1

    def assert_finance_sections_visible(self) -> None:
        for selector in [
            "#financeInvoicesSection",
            "#financeVatSection",
            "#financeIncomeTaxSection",
            "#financeInvoicesSummary",
            "#financeVatSummary",
            "#financeIncomeTaxSummary",
            "#financeInvoicesReportFilterNav",
            "#financeInvoicesLegend",
            "#financeIncomeTaxRate",
            "#financeIncomeTaxCalculateButton",
        ]:
            wait_for_visible(self.page, selector)
        assert self.page.locator("#financeInvoicesSelectionBar").count() >= 1

    def open_send_invoices_modal(self) -> None:
        self.page.locator("#financeInvoicesSendButton").click()
        wait_for_visible(self.page, "#financeInvoicesSendModal")
        wait_for_idle_ui(self.page)

    def assert_send_invoices_modal_surfaces(self) -> None:
        for selector in [
            "#financeInvoicesSendRecipients",
            "#financeInvoicesSendSubject",
            "#financeInvoicesSendMessage",
            "#financeInvoicesSendDueDatesToggle",
            "#financeInvoicesSendAttachmentOptions",
            "#financeInvoicesSendCancel",
            "#financeInvoicesSendTest",
            "#financeInvoicesSendConfirm",
        ]:
            wait_for_visible(self.page, selector)

    def open_override_modal_stub(self) -> None:
        self.page.evaluate(
            """
            () => {
              const modal = document.getElementById('financeInvoiceOverrideModal');
              const meta = document.getElementById('financeInvoiceOverrideMeta');
              const options = document.getElementById('financeInvoiceOverrideOptions');
              if (!modal) return;
              if (meta) {
                meta.textContent = 'בדיקת מודאל הוספה למועד דיווח.';
              }
              if (options) {
                options.innerHTML = `
                  <label class="marketing-doc-option">
                    <input type="checkbox" data-finance-override-due-date="15/07/2026" checked>
                    <span>15/07/2026</span>
                  </label>
                `;
              }
              modal.classList.add('visible');
              modal.setAttribute('aria-hidden', 'false');
            }
            """
        )
        wait_for_visible(self.page, "#financeInvoiceOverrideModal")

    def open_parse_modal_stub(self) -> None:
        self.page.evaluate(
            """
            () => {
              const modal = document.getElementById('financeInvoiceParseModal');
              const meta = document.getElementById('financeInvoiceParseMeta');
              const fields = document.getElementById('financeInvoiceParseFields');
              if (!modal) return;
              if (meta) {
                meta.innerHTML = 'קובץ מקור: <strong>sample.pdf</strong>';
              }
              if (fields) {
                fields.innerHTML = `
                  <label class="customer-create-field">
                    <span>ספק</span>
                    <input type="text" data-finance-parse-input="supplier_name" value="ספק לדוגמה">
                  </label>
                  <label class="customer-create-field">
                    <span>אסמכתא</span>
                    <input type="text" data-finance-parse-input="reference_number" value="INV-TEST-1">
                  </label>
                `;
              }
              modal.classList.add('visible');
              modal.setAttribute('aria-hidden', 'false');
            }
            """
        )
        wait_for_visible(self.page, "#financeInvoiceParseModal")

    def assert_parse_modal_surfaces(self) -> None:
        for selector in [
            "#financeInvoiceParseClose",
            "#financeInvoiceParseMeta",
            "#financeInvoiceParseFields",
            "#financeInvoiceParseCancel",
            "#financeInvoiceParseSave",
        ]:
            wait_for_visible(self.page, selector)

    def assert_override_modal_surfaces(self) -> None:
        for selector in [
            "#financeInvoiceOverrideClose",
            "#financeInvoiceOverrideMeta",
            "#financeInvoiceOverrideOptions",
            "#financeInvoiceOverrideCancel",
            "#financeInvoiceOverrideSave",
        ]:
            wait_for_visible(self.page, selector)
