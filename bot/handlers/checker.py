import io
import logging
import time

from telegram import InputFile, Update
from telegram.ext import CallbackQueryHandler, ContextTypes, MessageHandler, filters

from bot.database import Database
from bot.keyboards import BTN_CHECKER, CHECKER_CANCEL_KEYBOARD, MAIN_KEYBOARD, MAIN_KEYBOARD
from bot.utils.access import ensure_access
from bot.utils.proxy_checker import check_proxies, parse_proxies_from_text, progress_bar
from bot.utils.user_state import WAITING_CUSTOM_QTY, WAITING_PROXY_CHECK, is_menu_button

logger = logging.getLogger(__name__)

MAX_PROXIES_PER_CHECK = 200


def _checker_intro(daily_limit: int) -> str:
    return (
        "✅ <b>Proxy Checker Mode Active</b>\n\n"
        "Send me a list of proxies, or upload a <code>.txt</code> file, and I will check them "
        "concurrently for you. I will return a progress bar, summary, and clean "
        "<code>.txt</code> files containing working (live) and dead proxies.\n\n"
        "📝 <b>Supported Formats:</b>\n"
        "• <code>host:port</code>\n"
        "• <code>user:pass:host:port</code>\n"
        "• <code>host:port:user:pass</code>\n"
        "• <code>user:pass@host:port</code>\n\n"
        f"💡 <b>Limits:</b> Max {MAX_PROXIES_PER_CHECK} proxies per check, "
        f"up to {daily_limit} checks per 24 hours."
    )


def _is_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    user = update.effective_user
    return bool(user and user.id in context.bot_data["settings"].admin_ids)


def _daily_limit(context: ContextTypes.DEFAULT_TYPE) -> int:
    settings = context.bot_data["settings"]
    return int(getattr(settings, "checker_daily_limit", 5))


async def proxy_checker_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not await ensure_access(update, context):
        return

    context.user_data.pop(WAITING_CUSTOM_QTY, None)
    context.user_data[WAITING_PROXY_CHECK] = True

    try:
        await update.message.reply_text(
            _checker_intro(_daily_limit(context)),
            reply_markup=MAIN_KEYBOARD,
            parse_mode="HTML",
        )
        await update.message.reply_text(
            "Tap below to cancel checking:",
            reply_markup=CHECKER_CANCEL_KEYBOARD,
        )
    except Exception:
        logger.exception("Failed to send checker intro")
        await update.message.reply_text(
            "✅ Proxy Checker Mode Active\n\n"
            "Send proxies (one per line) or upload a .txt file.\n"
            "Formats: host:port | user:pass:host:port | host:port:user:pass | user:pass@host:port",
            reply_markup=MAIN_KEYBOARD,
        )
        await update.message.reply_text(
            "Tap below to cancel checking:",
            reply_markup=CHECKER_CANCEL_KEYBOARD,
        )


async def checker_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query:
        return
    await query.answer()
    context.user_data.pop(WAITING_PROXY_CHECK, None)
    await query.edit_message_text("❌ Proxy check cancelled.")
    if query.message:
        await query.message.reply_text(
            "Choose an option from the menu:",
            reply_markup=MAIN_KEYBOARD,
        )


async def _extract_proxy_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> str | None:
    message = update.message
    if not message:
        return None

    if message.document:
        doc = message.document
        if doc.file_size and doc.file_size > 512_000:
            await message.reply_text("File too large. Max size is 512 KB.")
            return None
        file = await context.bot.get_file(doc.file_id)
        data = await file.download_as_bytearray()
        return data.decode("utf-8", errors="ignore")

    if message.text:
        return message.text
    return None


async def _run_check(update: Update, context: ContextTypes.DEFAULT_TYPE, raw_text: str) -> None:
    message = update.message
    user = update.effective_user
    if not message or not user:
        return

    if not raw_text.strip():
        return

    db: Database = context.bot_data["db"]
    daily_limit = _daily_limit(context)
    proxies = parse_proxies_from_text(raw_text)

    if not proxies:
        await message.reply_text(
            "No valid proxies found.\n\n"
            "Supported formats:\n"
            "• host:port\n"
            "• user:pass:host:port\n"
            "• host:port:user:pass\n"
            "• user:pass@host:port"
        )
        return

    if len(proxies) > MAX_PROXIES_PER_CHECK:
        await message.reply_text(
            f"Too many proxies ({len(proxies)}). Max is {MAX_PROXIES_PER_CHECK} per check."
        )
        return

    if not _is_admin(update, context):
        used = db.count_proxy_checks_24h(user.id)
        if used >= daily_limit:
            await message.reply_text(
                f"⏳ Limit reached: {daily_limit} checks per 24 hours.\n"
                f"You have used {used}/{daily_limit}. Please try again later."
            )
            context.user_data.pop(WAITING_PROXY_CHECK, None)
            return

    context.user_data.pop(WAITING_PROXY_CHECK, None)
    total = len(proxies)
    status_msg = await message.reply_text(
        f"🔍 Checking <b>{total}</b> proxies...\n\n{progress_bar(0, total)}",
        parse_mode="HTML",
    )

    last_edit = 0.0

    async def on_progress(done: int, count: int) -> None:
        nonlocal last_edit
        now = time.monotonic()
        if done < count and now - last_edit < 1.5 and done % 20 != 0:
            return
        last_edit = now
        try:
            await status_msg.edit_text(
                f"🔍 Checking <b>{count}</b> proxies...\n\n{progress_bar(done, count)}",
                parse_mode="HTML",
            )
        except Exception:
            pass

    results = await check_proxies(proxies, on_progress=on_progress)

    live = [r.proxy for r in results if r.alive]
    dead = [r.proxy for r in results if not r.alive]

    if not _is_admin(update, context):
        db.record_proxy_check(user.id, total)

    summary = (
        "✅ <b>Check Complete</b>\n\n"
        f"<b>Total:</b> {len(results)}\n"
        f"<b>Live:</b> {len(live)} ✅\n"
        f"<b>Dead:</b> {len(dead)} ❌"
    )
    await status_msg.edit_text(
        f"{summary}\n\n{progress_bar(len(results), len(results))}",
        parse_mode="HTML",
    )
    await message.reply_text(summary, parse_mode="HTML")

    if live:
        live_file = InputFile(
            io.BytesIO("\n".join(live).encode("utf-8")),
            filename="live_proxies.txt",
        )
        await message.reply_document(live_file, caption=f"✅ {len(live)} live proxies")

    if dead:
        dead_file = InputFile(
            io.BytesIO("\n".join(dead).encode("utf-8")),
            filename="dead_proxies.txt",
        )
        await message.reply_document(dead_file, caption=f"❌ {len(dead)} dead proxies")


def _is_proxy_check_input(update: Update) -> bool:
    message = update.message
    if not message:
        return False
    if message.document:
        return True
    if message.text and not is_menu_button(message.text):
        return True
    return False


async def receive_proxies_to_check(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.user_data.get(WAITING_PROXY_CHECK):
        return
    if not update.message or not await ensure_access(update, context):
        return
    if not _is_proxy_check_input(update):
        return

    raw = await _extract_proxy_text(update, context)
    if raw is None:
        return
    await _run_check(update, context, raw)


def register_checker_handlers(application) -> None:
    application.add_handler(
        MessageHandler(filters.Text([BTN_CHECKER]), proxy_checker_start)
    )
    application.add_handler(CallbackQueryHandler(checker_cancel, pattern=r"^checker:cancel$"))
    application.add_handler(
        MessageHandler(
            (filters.TEXT | filters.Document.ALL) & ~filters.COMMAND,
            receive_proxies_to_check,
        ),
        group=2,
    )
