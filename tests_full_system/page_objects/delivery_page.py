from __future__ import annotations

from playwright.sync_api import Page

from tests_full_system.helpers.waits import wait_for_visible


class DeliveryPage:
    def __init__(self, page: Page) -> None:
        self.page = page

    def assert_core_actions_visible(self) -> None:
        for selector in [
            "#deliveryConfirmRefreshButton",
            "#deliveryConfirmUnsentButton",
            "#deliveryConfirmSentButton",
            "#deliveryConfirmSummary",
            "#deliveryContactsAddButton",
            "#deliveryContactsSummary",
        ]:
            wait_for_visible(self.page, selector)
        assert self.page.locator("#deliveryConfirmProgress").count() >= 1
        assert self.page.locator("#deliveryConfirmRowsHost").count() >= 1
        assert self.page.locator("#deliveryContactsRowsHost").count() >= 1

    def assert_upload_surface(self) -> None:
        for selector in [
            "#deliveryConfirmationUploadInput",
            "#deliveryConfirmProgressTitle",
            "#deliveryConfirmProgressPercent",
            "#deliveryConfirmProgressFill",
            "#deliveryConfirmProgressMessage",
        ]:
            assert self.page.locator(selector).count() >= 1

    def seed_delivery_rows_stub(self) -> None:
        self.page.evaluate(
            """
            () => {
              const host = document.getElementById('deliveryConfirmRowsHost');
              if (!host) return;
              host.innerHTML = `
                <tr>
                  <td>TEST | נעלולי פלא | חברה</td>
                  <td>TEST-PO-001</td>
                  <td>01/05/2026</td>
                  <td>550000</td>
                  <td>01/05/2026</td>
                  <td>TEST-signed.pdf</td>
                  <td>
                    <button type="button" data-delivery-upload="TEST-KEY">העלה אישור מסירה</button>
                    <button type="button" data-delivery-send="TEST-KEY">שלח</button>
                  </td>
                </tr>
              `;
            }
            """
        )
        wait_for_visible(self.page, '[data-delivery-upload="TEST-KEY"]')
        wait_for_visible(self.page, '[data-delivery-send="TEST-KEY"]')

    def seed_delivery_contacts_stub(self) -> None:
        self.page.evaluate(
            """
            () => {
              const host = document.getElementById('deliveryContactsRowsHost');
              if (!host) return;
              host.innerHTML = `
                <tr data-delivery-contact-index="0">
                  <td><button type="button" data-delivery-contact-edit-toggle="0">ערוך</button></td>
                  <td><input type="text" data-delivery-contact-field="company" data-delivery-contact-index="0" value="TEST | נעלולי פלא | חברה"></td>
                  <td><input type="text" data-delivery-contact-field="accounting_contact_name" data-delivery-contact-index="0" value="TEST | נעלולי פלא | הנהח"></td>
                  <td><input type="text" data-delivery-contact-field="phone" data-delivery-contact-index="0" value="04-0000000"></td>
                  <td><input type="text" data-delivery-contact-field="mobile" data-delivery-contact-index="0" value="0547720142"></td>
                  <td><input type="text" data-delivery-contact-field="email" data-delivery-contact-index="0" value="test@example.com"></td>
                </tr>
              `;
            }
            """
        )
        wait_for_visible(self.page, '[data-delivery-contact-edit-toggle="0"]')
        wait_for_visible(self.page, '[data-delivery-contact-field="company"]')
