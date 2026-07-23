import io

from telegram import InputFile, ReplyKeyboardRemove, Update
from telegram.ext import CallbackQueryHandler, CommandHandler, ContextTypes, MessageHandler, filters

from bot.database import Database
from bot.keyboards import (
    ADMIN_CANCEL_KEYBOARD,
    MAIN_KEYBOARD,
    admin_panel_keyboard,
    order_admin_keyboard,
)
from bot.utils.account_stock import (
    account_count_label,
    format_accounts_delivery_file,
    parse_accounts_from_text,
    parse_accounts_upload,
)
from bot.utils.broadcast import (
    BACK_ONLINE_NOTICE,
    MAINTENANCE_NOTICE,
    broadcast_message,
    format_announcement,
)
from bot.utils.order_messages import (
    order_delivered,
    order_proxy_caption,
    order_proxy_filename,
)
from bot.utils.user_state import (
    ADMIN_BROADCAST_TYPE,
    WAITING_ADMIN_BROADCAST,
    WAITING_ADMIN_PROXIES,
    clear_admin_modes,
    is_menu_button,
)


def _is_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    user = update.effective_user
    if not user:
        return False
    return user.id in context.bot_data["settings"].admin_ids


def _admin_panel_text(db: Database) -> str:
    maintenance = db.is_maintenance()
    stock = db.count_available_proxies()
    pending = len(db.get_pending_orders())
    return (
        "<b>🛠 Admin Panel</b>\n\n"
        f"Maintenance: <b>{'ON ⚠️' if maintenance else 'OFF ✅'}</b>\n"
        f"Account stock: <b>{stock}</b>\n"
        f"Pending orders: <b>{pending}</b>\n\n"
        "Use the buttons below to manage the bot."
    )


async def _send_admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    db: Database = context.bot_data["db"]
    text = _admin_panel_text(db)
    markup = admin_panel_keyboard()

    if update.callback_query:
        await update.callback_query.edit_message_text(
            text, reply_markup=markup, parse_mode="HTML"
        )
        return

    msg = update.effective_message
    if msg:
        await msg.reply_text(text, reply_markup=markup, parse_mode="HTML")


async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not _is_admin(update, context):
        return
    clear_admin_modes(context)
    await _send_admin_panel(update, context)


async def _enable_maintenance(context: ContextTypes.DEFAULT_TYPE) -> tuple[int, int]:
    db: Database = context.bot_data["db"]
    settings = context.bot_data["settings"]
    db.set_maintenance(True)
    return await broadcast_message(
        context.bot,
        db.get_all_user_ids(),
        MAINTENANCE_NOTICE,
        reply_markup=ReplyKeyboardRemove(),
        exclude_ids=set(settings.admin_ids),
    )


async def _disable_maintenance(context: ContextTypes.DEFAULT_TYPE) -> tuple[int, int]:
    db: Database = context.bot_data["db"]
    settings = context.bot_data["settings"]
    db.set_maintenance(False)
    return await broadcast_message(
        context.bot,
        db.get_all_user_ids(),
        BACK_ONLINE_NOTICE,
        reply_markup=MAIN_KEYBOARD,
        exclude_ids=set(settings.admin_ids),
    )


async def _run_broadcast(
    context: ContextTypes.DEFAULT_TYPE, text: str, *, kind: str = "broadcast"
) -> tuple[int, int, int]:
    db: Database = context.bot_data["db"]
    settings = context.bot_data["settings"]
    user_ids = db.get_all_user_ids()
    message = format_announcement(kind, text)
    sent, failed = await broadcast_message(
        context.bot,
        user_ids,
        message,
        parse_mode="HTML",
        reply_markup=MAIN_KEYBOARD,
        exclude_ids=set(settings.admin_ids),
    )
    return sent, failed, len(user_ids)


async def maintenance_on(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not _is_admin(update, context):
        return
    sent, failed = await _enable_maintenance(context)
    await update.message.reply_text(
        f"⚠️ Maintenance mode enabled.\n"
        f"Notice sent to {sent} user(s)."
        + (f" ({failed} unreachable)" if failed else "")
    )


async def maintenance_off(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not _is_admin(update, context):
        return
    sent, failed = await _disable_maintenance(context)
    await update.message.reply_text(
        f"🎉 Maintenance mode disabled.\n"
        f"Back-online notice sent to {sent} user(s)."
        + (f" ({failed} unreachable)" if failed else "")
    )


async def broadcast_notice(
    update: Update, context: ContextTypes.DEFAULT_TYPE, *, kind: str = "broadcast"
) -> None:
    if not update.message or not _is_admin(update, context):
        return

    text = ""
    if update.message.reply_to_message and update.message.reply_to_message.text:
        text = update.message.reply_to_message.text.strip()
    elif context.args:
        text = " ".join(context.args).strip()

    if not text:
        context.user_data[WAITING_ADMIN_BROADCAST] = True
        context.user_data[ADMIN_BROADCAST_TYPE] = kind
        icon = "📣" if kind == "notice" else "📢"
        label = "Notice" if kind == "notice" else "Broadcast"
        await update.message.reply_text(
            f"{icon} <b>{label} Mode</b>\n\n"
            "Send the message you want to deliver to all users.\n\n"
            "You can also use:\n"
            f"• <code>/{kind} Your message</code>\n"
            f"• Reply to a message with <code>/{kind}</code>",
            parse_mode="HTML",
            reply_markup=ADMIN_CANCEL_KEYBOARD,
        )
        return

    user_ids_total = len(context.bot_data["db"].get_all_user_ids())
    if not user_ids_total:
        await update.message.reply_text("No users in database yet.")
        return

    icon = "📣" if kind == "notice" else "📢"
    status = await update.message.reply_text(
        f"{icon} Sending {kind} to {user_ids_total} user(s)..."
    )
    sent, failed, _ = await _run_broadcast(context, text, kind=kind)
    await status.edit_text(
        f"{icon} {kind.title()} complete.\nSent: {sent}\nFailed: {failed}"
    )


async def broadcast_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await broadcast_notice(update, context, kind="broadcast")


async def notice_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await broadcast_notice(update, context, kind="notice")


async def show_stock(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not _is_admin(update, context):
        return
    db: Database = context.bot_data["db"]
    await update.message.reply_text(
        f"📦 Available accounts: {db.count_available_proxies()}"
    )


async def _send_pending_orders(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    db: Database = context.bot_data["db"]
    orders = db.get_pending_orders()
    chat_id = update.effective_chat.id if update.effective_chat else None
    if not chat_id:
        return

    if not orders:
        await context.bot.send_message(chat_id, "No pending orders.")
        return

    await context.bot.send_message(chat_id, f"📋 {len(orders)} pending order(s):")
    for order in orders:
        text = (
            f"Order #{order['id']}\n"
            f"User: {order['first_name']} (@{order['username'] or 'n/a'}) `{order['user_id']}`\n"
            f"Pack: {order['pack_name']} ({account_count_label(int(order['proxy_count']))})\n"
            f"Amount: ৳{order['amount']:.1f}\n"
            f"TRX: `{order['trx_id']}`"
        )
        await context.bot.send_message(
            chat_id,
            text,
            parse_mode="Markdown",
            reply_markup=order_admin_keyboard(order["id"]),
        )


async def show_pending(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not _is_admin(update, context):
        return
    await _send_pending_orders(update, context)


ADD_ACCOUNTS_HELP = (
    "➕ <b>Add Proxy Accounts</b>\n\n"
    "Upload your <code>.xlsx</code> Excel file here.\n\n"
    "<b>Excel columns:</b>\n"
    "• <b>Column B</b> = email\n"
    "• <b>Column C</b> = password\n\n"
    "<b>Or send text:</b>\n"
    "• <code>email@example.com:password</code> (one per line)\n\n"
    "Commands: <code>/add_accounts</code> or <code>/add_proxies</code>"
)


async def _download_document_bytes(update: Update, context: ContextTypes.DEFAULT_TYPE) -> tuple[str, bytes] | None:
    message = update.message
    if not message or not message.document:
        return None
    doc = message.document
    if doc.file_size and doc.file_size > 2_000_000:
        await message.reply_text("File too large. Max size is 2 MB.")
        return None
    filename = doc.file_name or "upload.txt"
    file = await context.bot.get_file(doc.file_id)
    data = await file.download_as_bytearray()
    return filename, bytes(data)


async def _add_accounts(
    update: Update, context: ContextTypes.DEFAULT_TYPE, accounts: list[str]
) -> None:
    if not accounts:
        msg = update.effective_message
        if msg:
            await msg.reply_text(
                "No valid accounts found.\n\n"
                "Excel: column B = email, column C = password\n"
                "Text: one <code>email:password</code> per line",
                parse_mode="HTML",
            )
        return

    db: Database = context.bot_data["db"]
    added = db.add_proxies(accounts)
    clear_admin_modes(context)

    msg = update.effective_message
    if msg:
        await msg.reply_text(
            f"✅ Added {added} account(s).\n"
            f"Total stock: {db.count_available_proxies()}"
        )


async def add_proxies_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not _is_admin(update, context):
        return

    reply = update.message.reply_to_message
    if reply and reply.document:
        doc = reply.document
        if doc.file_size and doc.file_size > 2_000_000:
            await update.message.reply_text("File too large. Max size is 2 MB.")
            return
        file = await context.bot.get_file(doc.file_id)
        data = await file.download_as_bytearray()
        accounts = parse_accounts_upload(doc.file_name or "upload.xlsx", bytes(data))
        await _add_accounts(update, context, accounts)
        return

    if update.message.document:
        downloaded = await _download_document_bytes(update, context)
        if downloaded:
            filename, data = downloaded
            accounts = parse_accounts_upload(filename, data)
            await _add_accounts(update, context, accounts)
        return

    text = ""
    if reply and reply.text:
        text = reply.text
    elif context.args:
        text = " ".join(context.args)

    if not text:
        context.user_data[WAITING_ADMIN_PROXIES] = True
        await update.message.reply_text(
            ADD_ACCOUNTS_HELP,
            parse_mode="HTML",
            reply_markup=ADMIN_CANCEL_KEYBOARD,
        )
        return

    await _add_accounts(update, context, parse_accounts_from_text(text))


async def admin_panel_action(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query or not query.data or not _is_admin(update, context):
        if query:
            await query.answer("Admin only.", show_alert=True)
        return

    action = query.data.split(":", 1)[1]
    await query.answer()

    if action == "cancel":
        clear_admin_modes(context)
        await query.edit_message_text("Admin panel closed.")
        return

    if action == "refresh":
        clear_admin_modes(context)
        await _send_admin_panel(update, context)
        return

    if action == "maint_on":
        sent, failed = await _enable_maintenance(context)
        await query.message.reply_text(
            f"⚠️ Maintenance mode enabled.\n"
            f"Notice sent to {sent} user(s)."
            + (f" ({failed} unreachable)" if failed else "")
        )
        await _send_admin_panel(update, context)
        return

    if action == "maint_off":
        sent, failed = await _disable_maintenance(context)
        await query.message.reply_text(
            f"🎉 Maintenance mode disabled.\n"
            f"Back-online notice sent to {sent} user(s)."
            + (f" ({failed} unreachable)" if failed else "")
        )
        await _send_admin_panel(update, context)
        return

    if action in ("broadcast", "notice"):
        clear_admin_modes(context)
        context.user_data[WAITING_ADMIN_BROADCAST] = True
        context.user_data[ADMIN_BROADCAST_TYPE] = action
        icon = "📣" if action == "notice" else "📢"
        label = "Notice" if action == "notice" else "Broadcast"
        await query.message.reply_text(
            f"{icon} <b>{label} Mode</b>\n\n"
            "Send the message you want to deliver to all users.",
            parse_mode="HTML",
            reply_markup=ADMIN_CANCEL_KEYBOARD,
        )
        return

    if action == "stock":
        db: Database = context.bot_data["db"]
        await query.message.reply_text(
            f"📦 Available accounts: {db.count_available_proxies()}"
        )
        return

    if action == "pending":
        await _send_pending_orders(update, context)
        return

    if action == "add_proxies":
        clear_admin_modes(context)
        context.user_data[WAITING_ADMIN_PROXIES] = True
        await query.message.reply_text(
            ADD_ACCOUNTS_HELP,
            parse_mode="HTML",
            reply_markup=ADMIN_CANCEL_KEYBOARD,
        )


async def receive_admin_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not _is_admin(update, context):
        return
    if not context.user_data.get(WAITING_ADMIN_BROADCAST):
        return
    if not update.message.text:
        return

    text = update.message.text.strip()
    if not text:
        return
    if is_menu_button(text):
        clear_admin_modes(context)
        return

    kind = context.user_data.pop(ADMIN_BROADCAST_TYPE, "broadcast")
    clear_admin_modes(context)
    user_ids_total = len(context.bot_data["db"].get_all_user_ids())
    if not user_ids_total:
        await update.message.reply_text("No users in database yet.")
        return

    icon = "📣" if kind == "notice" else "📢"
    status = await update.message.reply_text(
        f"{icon} Sending {kind} to {user_ids_total} user(s)..."
    )
    sent, failed, _ = await _run_broadcast(context, text, kind=kind)
    await status.edit_text(
        f"{icon} {kind.title()} complete.\nSent: {sent}\nFailed: {failed}"
    )


async def receive_admin_proxies(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not _is_admin(update, context):
        return
    if not context.user_data.get(WAITING_ADMIN_PROXIES):
        return

    if update.message.document:
        downloaded = await _download_document_bytes(update, context)
        if not downloaded:
            return
        filename, data = downloaded
        accounts = parse_accounts_upload(filename, data)
        await _add_accounts(update, context, accounts)
        return

    if update.message.text:
        text = update.message.text
        if is_menu_button(text):
            clear_admin_modes(context)
            return
        await _add_accounts(update, context, parse_accounts_from_text(text))


async def admin_order_action(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query or not query.data or not _is_admin(update, context):
        if query:
            await query.answer("Admin only.", show_alert=True)
        return
    await query.answer()

    parts = query.data.split(":")
    action = parts[1]
    order_id = int(parts[2])
    db: Database = context.bot_data["db"]
    order = db.get_order(order_id)
    if not order:
        await query.edit_message_text("Order not found.")
        return

    if action == "reject":
        if db.reject_order(order_id):
            await query.edit_message_text(f"Order #{order_id} rejected.")
            try:
                await context.bot.send_message(
                    order["user_id"],
                    f"❌ Order #{order_id} was rejected. Contact support if you paid.",
                )
            except Exception:
                pass
        return

    if action == "approve":
        proxies = db.get_available_proxies(order["proxy_count"])
        if len(proxies) < order["proxy_count"]:
            await query.answer(
                f"Not enough stock ({len(proxies)}/{order['proxy_count']})",
                show_alert=True,
            )
            return

        if db.approve_order(order_id, proxies):
            proxy_block = format_accounts_delivery_file(proxies)
            await query.edit_message_text(f"✅ Order #{order_id} approved.")
            try:
                proxy_count = int(order["proxy_count"])
                await context.bot.send_message(
                    order["user_id"],
                    order_delivered(order_id=order_id, proxy_count=proxy_count),
                    parse_mode="HTML",
                )
                await context.bot.send_document(
                    order["user_id"],
                    InputFile(
                        io.BytesIO(proxy_block.encode("utf-8")),
                        filename=order_proxy_filename(order_id),
                    ),
                    caption=order_proxy_caption(
                        order_id=order_id, proxy_count=proxy_count
                    ),
                )
            except Exception:
                pass
        else:
            await query.edit_message_text("Could not approve (already processed?).")


def register_admin_handlers(application) -> None:
    application.add_handler(CommandHandler("admin", admin_panel))
    application.add_handler(CommandHandler("maintenance_on", maintenance_on))
    application.add_handler(CommandHandler("maintenance_off", maintenance_off))
    application.add_handler(CommandHandler("broadcast", broadcast_command))
    application.add_handler(CommandHandler("notice", notice_command))
    application.add_handler(CommandHandler("stock", show_stock))
    application.add_handler(CommandHandler("pending", show_pending))
    application.add_handler(CommandHandler("add_proxies", add_proxies_command))
    application.add_handler(CommandHandler("add_accounts", add_proxies_command))
    application.add_handler(CallbackQueryHandler(admin_panel_action, pattern=r"^adminpanel:"))
    application.add_handler(CallbackQueryHandler(admin_order_action, pattern=r"^admin:"))
    application.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            receive_admin_broadcast,
        ),
        group=0,
    )
    application.add_handler(
        MessageHandler(
            (filters.TEXT | filters.Document.ALL) & ~filters.COMMAND,
            receive_admin_proxies,
        ),
        group=0,
    )
