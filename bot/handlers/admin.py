import io

from telegram import InputFile, ReplyKeyboardRemove, Update
from telegram.ext import CallbackQueryHandler, CommandHandler, ContextTypes, MessageHandler, filters

from bot.database import Database
from bot.keyboards import (
    ADMIN_CANCEL_KEYBOARD,
    MAIN_KEYBOARD,
    admin_panel_keyboard,
    order_admin_keyboard,
    stock_clear_confirm_keyboard,
    stock_manage_keyboard,
)
from bot.utils.account_stock import (
    account_count_label,
    find_account_line,
    format_accounts_delivery_file,
    format_stock_export_file,
    normalize_account_line,
    parse_accounts_from_text,
    parse_accounts_upload,
)
from bot.utils.admin_reports import (
    export_orders_csv,
    export_users_csv,
    format_order_summary_lines,
    format_store_stats_message,
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
    WAITING_ADMIN_STOCK_REPLACE,
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
    stats = db.get_store_stats()
    return (
        "<b>🛠 Admin Panel</b>\n\n"
        f"Maintenance: <b>{'ON ⚠️' if maintenance else 'OFF ✅'}</b>\n"
        f"Account stock: <b>{stock}</b>\n"
        f"Users: <b>{stats['total_users']}</b> · Orders: <b>{stats['total_orders']}</b>\n"
        f"Pending: <b>{stats['pending_orders']}</b> · Revenue: <b>৳{stats['revenue_bdt']:.1f}</b>\n\n"
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


def _stock_manage_message(db: Database) -> str:
    count = db.count_available_proxies()
    return (
        "<b>📦 Stock Manager</b>\n\n"
        f"Available accounts: <b>{count}</b>\n\n"
        "<b>Commands:</b>\n"
        "• <code>/stock_export</code> — download stock file\n"
        "• <code>/stock_delete login</code> — delete one account\n"
        "• <code>/stock_edit login newpassword</code> — change password\n"
        "• <code>/stock_replace</code> — replace all stock with new file\n\n"
        "Or use the buttons below."
    )


async def _send_stock_manager(
    update: Update, context: ContextTypes.DEFAULT_TYPE, *, edit: bool = False
) -> None:
    db: Database = context.bot_data["db"]
    text = _stock_manage_message(db)
    markup = stock_manage_keyboard()
    if edit and update.callback_query:
        await update.callback_query.edit_message_text(
            text, reply_markup=markup, parse_mode="HTML"
        )
        return
    msg = update.effective_message
    if msg:
        await msg.reply_text(text, reply_markup=markup, parse_mode="HTML")


async def _export_stock_file(
    context: ContextTypes.DEFAULT_TYPE, chat_id: int
) -> None:
    db: Database = context.bot_data["db"]
    items = db.list_available_stock()
    lines = [item["proxy_line"] for item in items]
    if not lines:
        await context.bot.send_message(chat_id, "No available accounts in stock.")
        return
    content = format_stock_export_file(lines)
    await context.bot.send_document(
        chat_id,
        InputFile(
            io.BytesIO(content.encode("utf-8")),
            filename="stock_accounts.txt",
        ),
        caption=f"📦 {len(lines)} available account(s)",
    )


async def show_stock(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not _is_admin(update, context):
        return
    await _send_stock_manager(update, context)


async def stock_export_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not _is_admin(update, context):
        return
    await _export_stock_file(context, update.message.chat_id)


async def stock_delete_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not _is_admin(update, context):
        return
    if not context.args:
        await update.message.reply_text(
            "Delete one unused account from stock.\n\n"
            "Usage:\n"
            "• <code>/stock_delete login</code>\n"
            "• <code>/stock_delete login:password</code>",
            parse_mode="HTML",
        )
        return

    db: Database = context.bot_data["db"]
    raw = " ".join(context.args).strip()
    line = normalize_account_line(raw)
    if not line:
        stock_lines = [item["proxy_line"] for item in db.list_available_stock()]
        line = find_account_line(stock_lines, raw)
    if not line:
        await update.message.reply_text("Account not found in available stock.")
        return
    if db.delete_available_by_line(line):
        await update.message.reply_text(
            f"✅ Deleted account.\nRemaining stock: {db.count_available_proxies()}"
        )
    else:
        await update.message.reply_text("Could not delete (already sold or missing).")


async def stock_edit_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not _is_admin(update, context):
        return
    if len(context.args) < 2:
        await update.message.reply_text(
            "Edit one unused account in stock.\n\n"
            "Usage:\n"
            "• <code>/stock_edit login newpassword</code>\n"
            "• <code>/stock_edit login:oldpass login:newpass</code>",
            parse_mode="HTML",
        )
        return

    db: Database = context.bot_data["db"]
    stock_lines = [item["proxy_line"] for item in db.list_available_stock()]
    old_raw = context.args[0]
    new_raw = " ".join(context.args[1:])

    old_line = normalize_account_line(old_raw)
    if not old_line:
        old_line = find_account_line(stock_lines, old_raw)
    if not old_line:
        await update.message.reply_text("Account not found in available stock.")
        return

    new_line = normalize_account_line(new_raw)
    if not new_line and ":" not in new_raw:
        login = old_line.split(":", 1)[0]
        new_line = normalize_account_line(f"{login}:{new_raw}")
    if not new_line:
        await update.message.reply_text("Invalid new account format.")
        return

    if db.update_available_by_line(old_line, new_line):
        await update.message.reply_text("✅ Account updated in stock.")
    else:
        await update.message.reply_text("Could not update (already sold or missing).")


async def stock_replace_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not _is_admin(update, context):
        return
    clear_admin_modes(context)
    context.user_data[WAITING_ADMIN_STOCK_REPLACE] = True
    await update.message.reply_text(
        "🔄 <b>Replace All Stock</b>\n\n"
        "This removes ALL unsold accounts and loads a new file.\n\n"
        "Upload <code>.csv</code> or <code>.xlsx</code> (column B = login, C = password).",
        parse_mode="HTML",
        reply_markup=ADMIN_CANCEL_KEYBOARD,
    )


async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not _is_admin(update, context):
        return
    db: Database = context.bot_data["db"]
    stats = db.get_store_stats()
    orders = db.get_recent_orders(limit=10)
    text = format_store_stats_message(stats)
    if orders:
        text += "\n\n" + format_order_summary_lines(orders, limit=5)
    await update.message.reply_text(text, parse_mode="HTML")


async def user_orders_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not _is_admin(update, context):
        return
    if not context.args or not context.args[0].isdigit():
        await update.message.reply_text(
            "Show all orders for one user.\n\nUsage: <code>/user_orders 123456789</code>",
            parse_mode="HTML",
        )
        return

    user_id = int(context.args[0])
    db: Database = context.bot_data["db"]
    user = db.get_user(user_id)
    orders = db.get_user_orders(user_id, limit=50)
    if not user:
        await update.message.reply_text("User not found.")
        return
    if not orders:
        await update.message.reply_text(
            f"No orders for {user.get('first_name')} (`{user_id}`).",
            parse_mode="Markdown",
        )
        return

    uname = f"@{user['username']}" if user.get("username") else f"id {user_id}"
    lines = [
        f"<b>👤 {user.get('first_name')}</b> ({uname})\n",
        f"Telegram ID: <code>{user_id}</code>\n",
    ]
    for o in orders:
        lines.append(
            f"<b>#{o['id']}</b> {o['pack_name']} · {o['proxy_count']} acct · "
            f"৳{float(o['amount']):.0f} · {o['status']}\n"
            f"TRX: <code>{o.get('trx_id') or '—'}</code>"
        )
    await update.message.reply_text("\n".join(lines), parse_mode="HTML")


async def _export_orders_file(context: ContextTypes.DEFAULT_TYPE, chat_id: int) -> None:
    db: Database = context.bot_data["db"]
    orders = db.get_recent_orders(limit=2000)
    if not orders:
        await context.bot.send_message(chat_id, "No orders yet.")
        return
    content = export_orders_csv(orders)
    await context.bot.send_document(
        chat_id,
        InputFile(
            io.BytesIO(content.encode("utf-8")),
            filename="all_orders.csv",
        ),
        caption=f"📋 {len(orders)} order(s)",
    )


async def _export_users_file(context: ContextTypes.DEFAULT_TYPE, chat_id: int) -> None:
    db: Database = context.bot_data["db"]
    users = db.list_users_with_order_stats(limit=5000)
    if not users:
        await context.bot.send_message(chat_id, "No users yet.")
        return
    content = export_users_csv(users)
    await context.bot.send_document(
        chat_id,
        InputFile(
            io.BytesIO(content.encode("utf-8")),
            filename="all_users.csv",
        ),
        caption=f"👥 {len(users)} user(s)",
    )


async def show_stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not _is_admin(update, context):
        return
    await stats_command(update, context)

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
    "Upload your <code>.xlsx</code> or <code>.csv</code> file here.\n\n"
    "<b>File columns:</b>\n"
    "• <b>Column B</b> = email or login\n"
    "• <b>Column C</b> = password\n\n"
    "<b>Or send text:</b>\n"
    "• <code>login:password</code> or <code>email@domain.com:password</code>\n\n"
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
                "File: column B = email/login, column C = password\n"
                "Supported: <code>.xlsx</code>, <code>.csv</code>, or text "
                "<code>login:password</code>",
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
        await _send_stock_manager(update, context, edit=True)
        return

    if action == "stock_export":
        chat_id = query.message.chat_id if query.message else None
        if chat_id:
            await _export_stock_file(context, chat_id)
        return

    if action == "stock_clear":
        db: Database = context.bot_data["db"]
        count = db.count_available_proxies()
        await query.message.reply_text(
            f"⚠️ Clear <b>{count}</b> unsold account(s) from stock?\n"
            "Sold accounts are not affected.",
            parse_mode="HTML",
            reply_markup=stock_clear_confirm_keyboard(),
        )
        return

    if action == "stock_clear_yes":
        db = context.bot_data["db"]
        removed = db.clear_available_stock()
        await query.message.reply_text(
            f"🗑 Cleared {removed} account(s) from stock.\n"
            f"Remaining: {db.count_available_proxies()}"
        )
        return

    if action == "stock_replace":
        clear_admin_modes(context)
        context.user_data[WAITING_ADMIN_STOCK_REPLACE] = True
        await query.message.reply_text(
            "🔄 <b>Replace All Stock</b>\n\n"
            "Upload <code>.csv</code> or <code>.xlsx</code> to replace all unsold accounts.",
            parse_mode="HTML",
            reply_markup=ADMIN_CANCEL_KEYBOARD,
        )
        return

    if action == "stats":
        db: Database = context.bot_data["db"]
        stats = db.get_store_stats()
        orders = db.get_recent_orders(limit=10)
        text = format_store_stats_message(stats)
        if orders:
            text += "\n\n" + format_order_summary_lines(orders, limit=5)
        await query.message.reply_text(text, parse_mode="HTML")
        return

    if action == "orders_export":
        chat_id = query.message.chat_id if query.message else None
        if chat_id:
            await _export_orders_file(context, chat_id)
        return

    if action == "users_export":
        chat_id = query.message.chat_id if query.message else None
        if chat_id:
            await _export_users_file(context, chat_id)
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

    if context.user_data.get(WAITING_ADMIN_STOCK_REPLACE):
        if update.message.document:
            downloaded = await _download_document_bytes(update, context)
            if not downloaded:
                return
            filename, data = downloaded
            accounts = parse_accounts_upload(filename, data)
            if not accounts:
                await update.message.reply_text(
                    "No valid accounts found in file.", parse_mode="HTML"
                )
                return
            db: Database = context.bot_data["db"]
            removed, added = db.replace_available_stock(accounts)
            clear_admin_modes(context)
            await update.message.reply_text(
                f"🔄 Stock replaced.\n"
                f"Removed: {removed}\n"
                f"Added: {added}\n"
                f"Total stock: {db.count_available_proxies()}"
            )
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
    application.add_handler(CommandHandler("stock_export", stock_export_command))
    application.add_handler(CommandHandler("stock_delete", stock_delete_command))
    application.add_handler(CommandHandler("stock_edit", stock_edit_command))
    application.add_handler(CommandHandler("stock_replace", stock_replace_command))
    application.add_handler(CommandHandler("stats", stats_command))
    application.add_handler(CommandHandler("user_orders", user_orders_command))
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
