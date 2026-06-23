from __future__ import annotations

from playwright.sync_api import Page

from tests_full_system.helpers.waits import wait_for_idle_ui, wait_for_visible


class InventoryPage:
    def __init__(self, page: Page) -> None:
        self.page = page

    def assert_core_actions_visible(self) -> None:
        for selector in [
            "#loadInventoryButton",
            "#inventoryMeasureCalculatorToggle",
            "#inventoryPurchaseOrdersOpenButton",
        ]:
            wait_for_visible(self.page, selector)

    def assert_sections_visible(self) -> None:
        for selector in [
            "#inventoryRawSection",
            "#inventoryFinishSection",
            "#inventoryContactsSection",
            "#inventoryPurchaseOrdersSection",
            "#inventorySupplierDeliverySection",
        ]:
            wait_for_visible(self.page, selector)

    def assert_raw_inventory_surface(self) -> None:
        for selector in [
            "#addRawInventoryButton",
            "#inventoryResetButton",
            "#inventorySummary",
            "#inventorySupplierAlphaNav",
            "#inventoryTableBody",
        ]:
            wait_for_visible(self.page, selector)

    def toggle_measure_calculator(self) -> None:
        self.page.locator("#inventoryMeasureCalculatorToggle").click()
        wait_for_idle_ui(self.page)
        wait_for_visible(self.page, "#inventoryMeasureCalculatorPanel")

    def assert_measure_calculator_surface(self) -> None:
        for selector in [
            "#inventoryMeasureModeSwitch",
            "#inventoryMeasureModeLinear",
            "#inventoryMeasureModeArea",
            "#inventoryMeasureValue",
            "#inventoryMeasureWidth",
            "#inventoryMeasureCalculateButton",
            "#inventoryMeasureWidthResult",
            "#inventoryMeasureLengthResult",
            "#inventoryMeasureAreaResult",
        ]:
            wait_for_visible(self.page, selector)

    def assert_finish_inventory_surface(self) -> None:
        for selector in [
            "#restoreRealStockButton",
            "#sandboxRestoreSummary",
            "#addFinishInventoryButton",
            "#finishInventorySummary",
            "#finishInventoryTableBody",
        ]:
            wait_for_visible(self.page, selector)
        for selector in [
            "#restoreProgress",
            "#restoreProgressFill",
            "#restoreProgressLabel",
        ]:
            assert self.page.locator(selector).count() >= 1

    def assert_supplier_contacts_surface(self) -> None:
        for selector in [
            "#addSupplierContactButton",
            "#supplierContactsSummary",
        ]:
            wait_for_visible(self.page, selector)
        assert self.page.locator("#supplierContactsTableBody").count() >= 1

    def assert_purchase_orders_surface(self) -> None:
        if self.page.locator("#inventoryPurchaseOrdersFormPanel:visible").count() == 0:
            self.page.locator("#inventoryPurchaseOrdersCreateButton").click()
            wait_for_idle_ui(self.page)
        for selector in [
            "#inventoryPurchaseOrdersRefreshButton",
            "#inventoryPurchaseOrdersSummary",
            "#inventoryPurchaseOrdersFormPanel",
            "#inventoryPoSupplierName",
            "#inventoryPoSupplierId",
            "#inventoryPoSupplierEmail",
            "#inventoryPoSupplierPhone",
            "#inventoryPoDate",
            "#inventoryPoItemSku",
            "#inventoryPoItemQuantity",
            "#inventoryPoItemUnit",
            "#inventoryPoItemDescription",
            "#inventoryPoItemUnitPrice",
            "#inventoryPoSubtotal",
            "#inventoryPoVat",
            "#inventoryPoTotal",
            "#inventoryPoRemarks",
            "#inventoryPoCreateSandboxButton",
            "#inventoryPoCreateProdButton",
            "#inventoryPurchaseOrdersLegend",
            "#inventoryPurchaseOrdersTableBody",
        ]:
            wait_for_visible(self.page, selector)
        for selector in [
            "#inventoryPurchaseOrdersCreateButton",
            "#inventoryPurchaseOrdersProgress",
            "#inventoryPurchaseOrdersProgressTitle",
            "#inventoryPurchaseOrdersProgressPercent",
            "#inventoryPurchaseOrdersProgressFill",
            "#inventoryPurchaseOrdersProgressMessage",
        ]:
            assert self.page.locator(selector).count() >= 1

    def assert_supplier_delivery_surface(self) -> None:
        for selector in [
            "#supplierDeliveryNoteUploadButton",
            "#supplierDeliveryNotesRefreshButton",
            "#supplierDeliveryNotesSummary",
            "#supplierDeliveryNotesAlphaNav",
        ]:
            wait_for_visible(self.page, selector)
        for selector in [
            "#supplierDeliveryNotesProgress",
            "#supplierDeliveryNotesProgressTitle",
            "#supplierDeliveryNotesProgressPercent",
            "#supplierDeliveryNotesProgressFill",
            "#supplierDeliveryNotesProgressMessage",
            "#supplierDeliveryNotesSummaryTableBody",
            "#supplierDeliveryNotesTableBody",
        ]:
            assert self.page.locator(selector).count() >= 1

    def open_supplier_delivery_editor_stub(self) -> None:
        self.page.evaluate(
            """
            () => {
              const editor = document.getElementById('supplierDeliveryNotesEditor');
              const fields = document.getElementById('supplierDeliveryNotesParsedFields');
              const itemsBody = document.getElementById('supplierDeliveryNotesParsedItemsBody');
              if (!editor) return;
              if (fields) {
                fields.innerHTML = `
                  <label class="customer-create-field">
                    <span>ספק</span>
                    <input type="text" data-supplier-note-top-field="supplier_name" value="ספק לדוגמה">
                  </label>
                `;
              }
              if (itemsBody) {
                itemsBody.innerHTML = `
                  <tr>
                    <td>1</td>
                    <td>—</td>
                    <td>SKU-1</td>
                    <td>פריט לדוגמה</td>
                    <td>מוצר</td>
                    <td>חומר</td>
                    <td>1</td>
                    <td>1</td>
                    <td>1</td>
                    <td>1</td>
                    <td>יח׳</td>
                    <td>הערה</td>
                  </tr>
                `;
              }
              editor.style.display = '';
            }
            """
        )
        wait_for_visible(self.page, "#supplierDeliveryNotesEditor")

    def assert_supplier_delivery_editor_surface(self) -> None:
        for selector in [
            "#supplierDeliveryNotesEditor",
            "#supplierDeliveryNotesSaveButton",
        ]:
            wait_for_visible(self.page, selector)
        for selector in [
            "#supplierDeliveryNotesParsedFields",
            "#supplierDeliveryNotesParsedItemsBody",
        ]:
            assert self.page.locator(selector).count() >= 1

    def open_purchase_order_send_modal_stub(self) -> None:
        self.page.evaluate(
            """
            () => {
              const modal = document.getElementById('inventoryPurchaseOrderSendModal');
              const meta = document.getElementById('inventoryPurchaseOrderSendMeta');
              const recipients = document.getElementById('inventoryPurchaseOrderRecipients');
              const phone = document.getElementById('inventoryPurchaseOrderPhone');
              const subject = document.getElementById('inventoryPurchaseOrderSubject');
              const message = document.getElementById('inventoryPurchaseOrderMessage');
              if (!modal) return;
              if (meta) meta.textContent = 'הזמנת רכש 1001 · ספק לדוגמה';
              if (recipients) recipients.value = 'supplier@example.com';
              if (phone) phone.value = '0500000000';
              if (subject) subject.value = 'הזמנת רכש לבדיקה';
              if (message) message.value = 'שלום, מצורפת הזמנת הרכש לבדיקה.';
              modal.classList.add('visible');
              modal.setAttribute('aria-hidden', 'false');
            }
            """
        )
        wait_for_visible(self.page, "#inventoryPurchaseOrderSendModal")

    def assert_purchase_order_send_modal_surfaces(self) -> None:
        for selector in [
            "#inventoryPurchaseOrderSendMeta",
            "#inventoryPurchaseOrderRecipients",
            "#inventoryPurchaseOrderPhone",
            "#inventoryPurchaseOrderSubject",
            "#inventoryPurchaseOrderMessage",
            "#inventoryPurchaseOrderSendCancel",
            "#inventoryPurchaseOrderTestSend",
            "#inventoryPurchaseOrderWhatsappSend",
            "#inventoryPurchaseOrderEmailSend",
        ]:
            wait_for_visible(self.page, selector)

    def open_purchase_order_delete_modal_stub(self) -> None:
        self.page.evaluate(
            """
            () => {
              const modal = document.getElementById('inventoryPurchaseOrderDeleteModal');
              const message = document.getElementById('inventoryPurchaseOrderDeleteMessage');
              const details = document.getElementById('inventoryPurchaseOrderDeleteDetails');
              if (!modal) return;
              if (message) message.textContent = 'למחוק את הזמנת הרכש הזו?';
              if (details) details.textContent = 'PO-1001 · ספק לדוגמה';
              modal.classList.add('visible');
              modal.setAttribute('aria-hidden', 'false');
            }
            """
        )
        wait_for_visible(self.page, "#inventoryPurchaseOrderDeleteModal")

    def assert_purchase_order_delete_modal_surfaces(self) -> None:
        for selector in [
            "#inventoryPurchaseOrderDeleteMessage",
            "#inventoryPurchaseOrderDeleteDetails",
            "#inventoryPurchaseOrderDeleteCancel",
            "#inventoryPurchaseOrderDeleteConfirm",
        ]:
            wait_for_visible(self.page, selector)
