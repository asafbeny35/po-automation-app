import re
import asyncio
from pathlib import Path
from urllib.parse import quote

try:
    from playwright.async_api import async_playwright
    _PLAYWRIGHT_AVAILABLE = True
except ImportError:
    async_playwright = None  # type: ignore[assignment]
    _PLAYWRIGHT_AVAILABLE = False


def _normalize_ws(value: str) -> str:
    return " ".join((value or "").split()).strip()

_WHATSAPP_PLAYWRIGHT = None
_WHATSAPP_CONTEXT = None
_WHATSAPP_CONTEXT_LOCK = asyncio.Lock()


def _normalize_phone(phone: str) -> str:
    digits = re.sub(r"\D", "", phone or "")
    if digits.startswith("0"):
        digits = "972" + digits[1:]
    return digits


def _file_send_wait_ms(path: Path) -> int:
    try:
        size_mb = max(path.stat().st_size, 1) / (1024 * 1024)
    except Exception:
        size_mb = 1
    dynamic_wait = 7000 + int(size_mb * 4500)
    return max(8000, min(dynamic_wait, 30000))


def _file_post_send_wait_ms(path: Path) -> int:
    try:
        size_mb = max(path.stat().st_size, 1) / (1024 * 1024)
    except Exception:
        size_mb = 1
    dynamic_wait = 14000 + int(size_mb * 7000)
    return max(18000, min(dynamic_wait, 60000))


async def _get_whatsapp_context_and_page():
    if not _PLAYWRIGHT_AVAILABLE:
        raise RuntimeError("WhatsApp Web אינו זמין בסביבת serverless (Playwright לא מותקן)")

    profile_dir = Path.home() / "Downloads" / "po_automation_app" / "whatsapp-profile"
    profile_dir.mkdir(parents=True, exist_ok=True)

    global _WHATSAPP_PLAYWRIGHT, _WHATSAPP_CONTEXT
    async with _WHATSAPP_CONTEXT_LOCK:
        context = _WHATSAPP_CONTEXT
        try:
            if context is not None:
                _ = context.pages
        except Exception:
            context = None
            _WHATSAPP_CONTEXT = None

        if context is None:
            _WHATSAPP_PLAYWRIGHT = await async_playwright().start()
            context = await _WHATSAPP_PLAYWRIGHT.chromium.launch_persistent_context(
                user_data_dir=str(profile_dir),
                headless=False,
                slow_mo=60,
                args=[
                    "--disable-session-crashed-bubble",
                    "--hide-crash-restore-bubble",
                ],
            )
            _WHATSAPP_CONTEXT = context

        pages = [page for page in context.pages if not page.is_closed()]
        page = pages[0] if pages else await context.new_page()
        await page.bring_to_front()
        return context, page


async def send_files_via_whatsapp(phone: str, message: str, file_paths: list[str]):
    phone = _normalize_phone(phone)
    context, page = await _get_whatsapp_context_and_page()
    try:
        send_url = f"https://web.whatsapp.com/send?phone={phone}"
        if message:
            send_url += f"&text={quote(message)}"

        await page.goto(send_url, wait_until="domcontentloaded", timeout=30000)
        await page.bring_to_front()

        send_icon = page.locator(
            "span[data-icon='send'], "
            "button[aria-label='Send'], "
            "button[aria-label^='Send '], "
            "div[role='button'][aria-label='Send'], "
            "div[role='button'][aria-label^='Send ']"
        )
        attach_button = page.locator("button[aria-label='Attach']")
        message_box = page.locator(
            "footer div[contenteditable='true'], "
            "div[contenteditable='true'][data-tab='10'], "
            "div[contenteditable='true'][role='textbox'], "
            "div[contenteditable='true']"
        ).last

        async def _body_text() -> str:
            try:
                return await page.locator("body").inner_text()
            except Exception:
                return ""

        async def _chat_ready() -> bool:
            try:
                if await attach_button.count():
                    if await attach_button.first.is_visible():
                        return True
            except Exception:
                pass
            try:
                if await message_box.count():
                    if await message_box.is_visible():
                        return True
            except Exception:
                pass
            try:
                if await send_icon.count():
                    if await send_icon.first.is_visible():
                        return True
            except Exception:
                pass
            return False

        async def _wait_for_chat_ready() -> None:
            downloading_seen = False
            last_body_text = ""
            for attempt in range(360):
                if await _chat_ready():
                    return
                if attempt % 4 == 0:
                    last_body_text = await _body_text()
                    if "Your messages are downloading" in last_body_text:
                        downloading_seen = True
                wait_ms = 1000 if downloading_seen else 500
                await page.wait_for_timeout(wait_ms)
            reason = "WhatsApp chat composer did not become ready in time"
            if downloading_seen:
                reason += " (messages were still downloading)"
            if last_body_text:
                compact = " ".join(last_body_text.split())
                if compact:
                    reason += f": {compact[:240]}"
            raise RuntimeError(reason)
        await _wait_for_chat_ready()

        # הודעה
        if message:
            try:
                await send_icon.first.wait_for(timeout=15000)
                await send_icon.first.click()
            except Exception:
                try:
                    await message_box.wait_for(timeout=15000)
                    current_text = ""
                    try:
                        current_text = _normalize_ws(await message_box.inner_text())
                    except Exception:
                        current_text = ""
                    if not current_text:
                        await message_box.fill(message)
                    await page.keyboard.press("Enter")
                except Exception:
                    await page.keyboard.press("Enter")

            # המתנה קצרה בלבד כדי לאפשר לוואטסאפ לרשום את ההודעה לפני צירוף הקובץ.
            await page.wait_for_timeout(1200)

        async def _preview_still_open(preview_locator) -> bool:
            try:
                return await preview_locator.is_visible()
            except Exception:
                return False

        async def _click_attachment_send_button(send_locator) -> bool:
            click_attempts = [
                {"force": False, "delay": 0},
                {"force": True, "delay": 150},
            ]
            for attempt in click_attempts:
                try:
                    if attempt["delay"]:
                        await page.wait_for_timeout(attempt["delay"])
                    await send_locator.click(timeout=4000, force=attempt["force"])
                    await page.wait_for_timeout(900)
                    return True
                except Exception:
                    continue
            return False

        # קובץ
        for path in file_paths:
            file_path = Path(path)
            print(f"📎 sending file: {file_path}")

            # פתיחת attach
            await attach_button.first.wait_for(timeout=30000)
            await attach_button.first.click()
            await page.wait_for_timeout(250)

            # 🔥 file chooser אמיתי
            async with page.expect_file_chooser() as fc_info:
                await page.get_by_role("menuitem", name="Document").click()

            file_chooser = await fc_info.value
            await file_chooser.set_files(str(file_path))

            # ב-WhatsApp Business Desktop/Web החדש אזור הצרופה לא נפתח כ-dialog,
            # אלא כחלק מאזור הצ'אט עצמו. לכן מחפשים את רכיבי התצוגה המקדימה הגלובליים.
            preview_thumbnail = page.locator(
                "div[role='tab'][aria-label^='Document thumbnail'], "
                "div[role='tab'][aria-label^='Open document'], "
                "div[role='button'][aria-label^='Open document']"
            ).last
            remove_attachment_button = page.locator("div[role='button'][aria-label='Remove attachment']").last
            add_file_button = page.locator("button[aria-label='Add file']").last
            attachment_send_button = page.locator(
                "div[role='button'][aria-label='Send'], "
                "div[role='button'][aria-label^='Send '], "
                "button[aria-label='Send'], "
                "button[aria-label^='Send ']"
            ).last

            await attachment_send_button.wait_for(timeout=30000)
            await preview_thumbnail.wait_for(timeout=30000)
            await page.wait_for_timeout(max(2500, _file_send_wait_ms(file_path) - 3500))

            await page.bring_to_front()
            await page.wait_for_timeout(120)

            async def _focus_preview_thumbnail() -> None:
                try:
                    await preview_thumbnail.evaluate(
                        """
                        element => {
                          element.scrollIntoView({ block: 'center', inline: 'center' });
                          element.focus();
                        }
                        """
                    )
                except Exception:
                    try:
                        await preview_thumbnail.focus()
                    except Exception:
                        try:
                            await preview_thumbnail.click(force=True)
                        except Exception:
                            pass
                await page.wait_for_timeout(120)

            # במסלולים מסוימים של קובץ בלבד, לחיצה ישירה על כפתור השליחה עובדת
            # טוב יותר מהתקדמות בטאבים. ננסה קודם את המסלול הישיר.
            direct_clicked = await _click_attachment_send_button(attachment_send_button)
            if direct_clicked:
                for _ in range(16):
                    if not await _preview_still_open(preview_thumbnail):
                        break
                    await page.wait_for_timeout(250)

            # מסלול השליחה הראשי לפי הלוג האמיתי אצלך:
            # focus thumbnail -> body -> thumbnail -> remove attachment -> add file -> send
            if await _preview_still_open(preview_thumbnail):
                await _focus_preview_thumbnail()
                for _ in range(5):
                    await page.keyboard.press("Tab")
                    await page.wait_for_timeout(350)
                await page.keyboard.press("Enter")

            # אם אזור הצרופה עדיין פתוח, מריצים שוב את אותו המסלול בדיוק.
            if await _preview_still_open(preview_thumbnail):
                await _focus_preview_thumbnail()
                for _ in range(5):
                    await page.keyboard.press("Tab")
                    await page.wait_for_timeout(180)
                await page.keyboard.press("Enter")

            # אם גם אחרי שני סבבי הטאבים אזור הצרופה עדיין פתוח,
            # נבצע fallback ישיר לכפתור השליחה.
            if await _preview_still_open(preview_thumbnail):
                await _click_attachment_send_button(attachment_send_button)

            # חכה שהתצוגה המקדימה תיסגר אם אפשר; אם לא, עדיין נמשיך להמתנה ארוכה.
            for _ in range(30):
                if not await _preview_still_open(preview_thumbnail):
                    break
                await page.wait_for_timeout(250)

            if await _preview_still_open(preview_thumbnail):
                raise RuntimeError(f"WhatsApp attachment preview did not close after send attempt for {file_path.name}")

            # זה החלק הקריטי: לא לסגור את החלון לפני שהקובץ באמת הספיק להיטען ולהישלח.
            await page.wait_for_timeout(_file_post_send_wait_ms(file_path))

        print("✅ all files sent")

        # השאר את החלון פתוח עוד קצת אחרי הצירוף האחרון,
        # כדי ש-WhatsApp יסיים ממש את ההעלאה/השליחה לפני סגירה.
        await page.wait_for_timeout(10000)
        try:
            if not page.is_closed():
                await page.close()
        except Exception:
            pass
    except Exception:
        try:
            await page.bring_to_front()
        except Exception:
            pass
        raise
