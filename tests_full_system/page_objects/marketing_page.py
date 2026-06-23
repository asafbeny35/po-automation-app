from __future__ import annotations

from playwright.sync_api import Page

from tests_full_system.helpers.waits import wait_for_idle_ui, wait_for_visible


class MarketingPage:
    def __init__(self, page: Page) -> None:
        self.page = page

    def assert_core_actions_visible(self) -> None:
        for selector in [
            "#marketingLoadButton",
            "#marketingWorkManagersLoadButton",
            "#marketingConstructionCompaniesLoadButton",
        ]:
            wait_for_visible(self.page, selector)

    def assert_sections_visible(self) -> None:
        for selector in [
            "#marketingSummary",
            "#marketingKpiSection",
            "#marketingPipelineSection",
            "#marketingWorkManagersSection",
            "#marketingConstructionCompaniesSection",
            "#marketingRemindersSection",
            "#marketingHistorySection",
            "#marketingDocsSection",
        ]:
            wait_for_visible(self.page, selector)

    def assert_pipeline_surface(self) -> None:
        for selector in [
            "#marketingPipelineToggle",
            "#marketingPipelineContent",
            "#marketingPipelineLegend",
            "#marketingPipelineAlphaNav",
        ]:
            wait_for_visible(self.page, selector)
        for selector in [
            "#marketingPipelineProgress",
            "#marketingPipelineProgressTitle",
            "#marketingPipelineProgressPercent",
            "#marketingPipelineProgressFill",
            "#marketingPipelineProgressMessage",
            "#marketingAudienceList",
        ]:
            assert self.page.locator(selector).count() >= 1

    def assert_work_managers_surface(self) -> None:
        for selector in [
            "#marketingWorkManagersCollapseButton",
            "#marketingWorkManagersAddButton",
            "#marketingWorkManagersCopyPhonesButton",
            "#marketingWorkManagersCopyEmailsButton",
            "#marketingWorkManagersExportCsvButton",
            "#marketingWorkManagersContent",
            "#marketingWorkManagersAlphaMode",
            "#marketingWorkManagersActiveOnlyButton",
            "#marketingWorkManagersAlphaNav",
            "#marketingWorkManagersSummary",
        ]:
            wait_for_visible(self.page, selector)
        for selector in [
            "#marketingWorkManagersSaveProgress",
            "#marketingWorkManagersSaveProgressTitle",
            "#marketingWorkManagersSaveProgressPercent",
            "#marketingWorkManagersSaveProgressFill",
            "#marketingWorkManagersSaveProgressMessage",
            "#marketingWorkManagersSelectionBar",
            "#marketingWorkManagersClearSelection",
            "#marketingWorkManagersBulkDelete",
            "#marketingWorkManagersBulkSend",
            "#marketingWorkManagersTableBody",
        ]:
            assert self.page.locator(selector).count() >= 1

    def assert_construction_companies_surface(self) -> None:
        for selector in [
            "#marketingConstructionCompaniesCollapseButton",
            "#marketingConstructionCompaniesAddButton",
            "#marketingConstructionCompaniesCopyPhonesButton",
            "#marketingConstructionCompaniesCopyEmailsButton",
            "#marketingConstructionCompaniesContent",
            "#marketingConstructionCompaniesAlphaMode",
            "#marketingConstructionCompaniesAlphaNav",
            "#marketingConstructionCompaniesSummary",
        ]:
            wait_for_visible(self.page, selector)
        for selector in [
            "#marketingConstructionCompaniesSaveProgress",
            "#marketingConstructionCompaniesSaveProgressTitle",
            "#marketingConstructionCompaniesSaveProgressPercent",
            "#marketingConstructionCompaniesSaveProgressFill",
            "#marketingConstructionCompaniesSaveProgressMessage",
            "#marketingConstructionCompaniesSelectionBar",
            "#marketingConstructionCompaniesClearSelection",
            "#marketingConstructionCompaniesBulkDelete",
            "#marketingConstructionCompaniesBulkSend",
            "#marketingConstructionCompaniesTableBody",
        ]:
            assert self.page.locator(selector).count() >= 1

    def assert_reminders_surface(self) -> None:
        for selector in [
            "#marketingRemindersLoadButton",
            "#marketingRemindersCollapseButton",
            "#marketingReminderAddButton",
            "#marketingRemindersContent",
            "#marketingRemindersLegend",
        ]:
            wait_for_visible(self.page, selector)
        for selector in [
            "#marketingRemindersSaveProgress",
            "#marketingRemindersSaveProgressTitle",
            "#marketingRemindersSaveProgressPercent",
            "#marketingRemindersSaveProgressFill",
            "#marketingRemindersSaveProgressMessage",
            "#marketingRemindersList",
        ]:
            assert self.page.locator(selector).count() >= 1

    def assert_history_and_docs_surface(self) -> None:
        for selector in [
            "#marketingHistoryLoadButton",
            "#marketingHistoryCollapseButton",
            "#marketingHistoryContent",
            "#marketingDocsToggleButton",
            "#marketingDocsRefreshButton",
        ]:
            wait_for_visible(self.page, selector)
        for selector in [
            "#marketingHistoryList",
            "#marketingDocsList",
        ]:
            assert self.page.locator(selector).count() >= 1

    def toggle_pipeline(self) -> None:
        self.page.locator("#marketingPipelineToggle").click()
        wait_for_idle_ui(self.page)

    def open_mail_modal_stub(self) -> None:
        self.page.evaluate(
            """
            () => {
              const modal = document.getElementById('marketingMailModal');
              const meta = document.getElementById('marketingMailMeta');
              const recipients = document.getElementById('marketingMailRecipients');
              const subject = document.getElementById('marketingMailSubject');
              const editor = document.getElementById('marketingMailEditor');
              if (!modal) return;
              if (meta) meta.textContent = 'שליחת מייל שיווקי ללקוח לדוגמה';
              if (recipients) recipients.value = 'customer@example.com';
              if (subject) subject.value = 'מסמך שיווקי לבדיקה';
              if (editor) editor.innerHTML = '<p>היי, מצורף מסמך שיווקי לבדיקה.</p>';
              modal.classList.add('visible');
              modal.setAttribute('aria-hidden', 'false');
            }
            """
        )
        wait_for_visible(self.page, "#marketingMailModal")

    def assert_mail_modal_surface(self) -> None:
        for selector in [
            "#marketingMailMeta",
            "#marketingMailRecipients",
            "#marketingMailSubject",
            "#marketingMailEditor",
            "#marketingMailDocToggle",
            "#marketingMailAttachments",
            "#marketingMailCancel",
            "#marketingMailTestSend",
            "#marketingMailSend",
        ]:
            wait_for_visible(self.page, selector)

    def open_doc_whatsapp_modal_stub(self) -> None:
        self.page.evaluate(
            """
            () => {
              const modal = document.getElementById('marketingDocWhatsappModal');
              const meta = document.getElementById('marketingDocWhatsappMeta');
              const phone = document.getElementById('marketingDocWhatsappPhone');
              const message = document.getElementById('marketingDocWhatsappMessage');
              if (!modal) return;
              if (meta) meta.textContent = 'שליחת מסמך שיווקי בוואטסאפ';
              if (phone) phone.value = '0500000000';
              if (message) message.value = 'שלום, מצורף מסמך שיווקי לבדיקה.';
              modal.classList.add('visible');
              modal.setAttribute('aria-hidden', 'false');
            }
            """
        )
        wait_for_visible(self.page, "#marketingDocWhatsappModal")

    def assert_doc_whatsapp_modal_surface(self) -> None:
        for selector in [
            "#marketingDocWhatsappMeta",
            "#marketingDocWhatsappPhone",
            "#marketingDocWhatsappMessage",
            "#marketingDocWhatsappCancel",
            "#marketingDocWhatsappSend",
        ]:
            wait_for_visible(self.page, selector)

    def open_comm_modal_stub(self) -> None:
        self.page.evaluate(
            """
            () => {
              const modal = document.getElementById('marketingCommModal');
              const meta = document.getElementById('marketingCommMeta');
              const email = document.getElementById('marketingCommEmail');
              const phone = document.getElementById('marketingCommPhone');
              const subject = document.getElementById('marketingCommSubject');
              const message = document.getElementById('marketingCommMessage');
              if (!modal) return;
              if (meta) meta.textContent = 'פעולת תקשורת ללקוח לדוגמה';
              if (email) email.value = 'customer@example.com';
              if (phone) phone.value = '0500000000';
              if (subject) subject.value = 'בדיקת תקשורת';
              if (message) message.value = 'שלום, זו בדיקת תקשורת.';
              modal.classList.add('visible');
              modal.setAttribute('aria-hidden', 'false');
            }
            """
        )
        wait_for_visible(self.page, "#marketingCommModal")

    def assert_comm_modal_surface(self) -> None:
        for selector in [
            "#marketingCommMeta",
            "#marketingCommEmail",
            "#marketingCommPhone",
            "#marketingCommSubject",
            "#marketingCommMessage",
            "#marketingCommCancel",
            "#marketingCommSendEmail",
            "#marketingCommSendWhatsapp",
        ]:
            wait_for_visible(self.page, selector)

    def open_reminder_modal_stub(self) -> None:
        self.page.evaluate(
            """
            () => {
              const modal = document.getElementById('marketingReminderModal');
              const meta = document.getElementById('marketingReminderMeta');
              const customerName = document.getElementById('marketingReminderCustomerName');
              const contactName = document.getElementById('marketingReminderContactName');
              const phone = document.getElementById('marketingReminderPhone');
              const email = document.getElementById('marketingReminderEmail');
              const note = document.getElementById('marketingReminderNoteText');
              const message = document.getElementById('marketingReminderMessage');
              if (!modal) return;
              if (meta) meta.textContent = 'יצירת תזכורת ללקוח לדוגמה';
              if (customerName) customerName.value = 'לקוח לדוגמה';
              if (contactName) contactName.value = 'איש קשר';
              if (phone) phone.value = '0500000000';
              if (email) email.value = 'customer@example.com';
              if (note) note.value = 'בדיקת תזכורת';
              if (message) message.value = 'צריך לחזור ללקוח בנושא ההצעה.';
              modal.classList.add('visible');
              modal.setAttribute('aria-hidden', 'false');
            }
            """
        )
        wait_for_visible(self.page, "#marketingReminderModal")

    def assert_reminder_modal_surface(self) -> None:
        for selector in [
            "#marketingReminderMeta",
            "#marketingReminderCustomerName",
            "#marketingReminderContactName",
            "#marketingReminderPhone",
            "#marketingReminderEmail",
            "#marketingReminderNoteText",
            "#marketingReminderDueDate",
            "#marketingReminderDueTime",
            "#marketingReminderChannel",
            "#marketingReminderMessage",
            "#marketingReminderCancel",
            "#marketingReminderSave",
        ]:
            wait_for_visible(self.page, selector)

    def open_work_managers_send_modal_stub(self) -> None:
        self.page.evaluate(
            """
            () => {
              const modal = document.getElementById('marketingWorkManagersSendModal');
              const meta = document.getElementById('marketingWorkManagersSendMeta');
              const emails = document.getElementById('marketingWorkManagersSendEmails');
              const phones = document.getElementById('marketingWorkManagersSendPhones');
              const subject = document.getElementById('marketingWorkManagersSendSubject');
              const message = document.getElementById('marketingWorkManagersSendMessage');
              if (!modal) return;
              if (meta) meta.textContent = 'שליחה למנהלי עבודה';
              if (emails) emails.value = 'manager@example.com';
              if (phones) phones.value = '0500000000';
              if (subject) subject.value = 'מסמך שיווקי';
              if (message) message.value = 'שלום, מצורף מסמך שיווקי לבדיקה.';
              modal.classList.add('visible');
              modal.setAttribute('aria-hidden', 'false');
            }
            """
        )
        wait_for_visible(self.page, "#marketingWorkManagersSendModal")

    def assert_work_managers_send_modal_surface(self) -> None:
        for selector in [
            "#marketingWorkManagersSendMeta",
            "#marketingWorkManagersSendEmails",
            "#marketingWorkManagersSendPhones",
            "#marketingWorkManagersSendSubject",
            "#marketingWorkManagersSendMessage",
            "#marketingWorkManagersSendCancel",
            "#marketingWorkManagersSendWhatsapp",
            "#marketingWorkManagersSendEmail",
        ]:
            wait_for_visible(self.page, selector)

    def open_construction_companies_send_modal_stub(self) -> None:
        self.page.evaluate(
            """
            () => {
              const modal = document.getElementById('marketingConstructionCompaniesSendModal');
              const meta = document.getElementById('marketingConstructionCompaniesSendMeta');
              const emails = document.getElementById('marketingConstructionCompaniesSendEmails');
              const phones = document.getElementById('marketingConstructionCompaniesSendPhones');
              const subject = document.getElementById('marketingConstructionCompaniesSendSubject');
              const message = document.getElementById('marketingConstructionCompaniesSendMessage');
              if (!modal) return;
              if (meta) meta.textContent = 'שליחה לחברת בנייה';
              if (emails) emails.value = 'company@example.com';
              if (phones) phones.value = '0500000000';
              if (subject) subject.value = 'מסמך שיווקי';
              if (message) message.value = 'שלום, מצורף מסמך שיווקי לבדיקה.';
              modal.classList.add('visible');
              modal.setAttribute('aria-hidden', 'false');
            }
            """
        )
        wait_for_visible(self.page, "#marketingConstructionCompaniesSendModal")

    def assert_construction_companies_send_modal_surface(self) -> None:
        for selector in [
            "#marketingConstructionCompaniesSendMeta",
            "#marketingConstructionCompaniesSendEmails",
            "#marketingConstructionCompaniesSendPhones",
            "#marketingConstructionCompaniesSendSubject",
            "#marketingConstructionCompaniesSendMessage",
            "#marketingConstructionCompaniesSendCancel",
            "#marketingConstructionCompaniesSendWhatsapp",
            "#marketingConstructionCompaniesSendEmail",
        ]:
            wait_for_visible(self.page, selector)
