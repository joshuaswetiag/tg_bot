import io

from telegram import InputFile, Update
from telegram.ext import CallbackQueryHandler, CommandHandler, ContextTypes, MessageHandler, filters

from bot.database import Database
from bot.keyboards import (
    ADMIN_CANCEL_KEYBOARD,
    admin_panel_keyboard,
    order_admin_keyboard,
)
from bot.utils.broadcast import BACK_ONLINE_NOTICE, MAINTENANCE_NOTICE, broadcast_message
from bot.utils.order_messages import (
    order_delivered,
    order_proxy_caption,
    order_proxy_filename,
)
from bot.utils.user_state import (
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
        f"Proxy stock: <b>{stock}</b>\n"
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
        exclude_ids=set(settings.admin_ids),
    )


async def _run_broadcast(context: ContextTypes.DEFAULT_TYPE, text: str) -> tuple[int, int, int]:
    db: Database = context.bot_data["db"]
    settings = context.bot_data["settings"]
    user_ids = db.get_all_user_ids()
    sent, failed = await broadcast_message(
        context.bot,
        user_ids,
        text,
        parse_mode=None,
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


async def broadcast_notice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not _is_admin(update, context):
        return

    text = ""
    if update.message.reply_to_message and update.message.reply_to_message.text:
        text = update.message.reply_to_message.text.strip()
    elif context.args:
        text = " ".join(context.args).strip()

    if not text:
        context.user_data[WAITING_ADMIN_BROADCAST] = True
        await update.message.reply_text(
            "📢 <b>Broadcast Mode</b>\n\n"
            "Send the message you want to deliver to all users.\n\n"
            "You can also use:\n"
            "• <code>/broadcast Your message</code>\n"
            "• Reply to a message with <code>/broadcast</code>",
            parse_mode="HTML",
            reply_markup=ADMIN_CANCEL_KEYBOARD,
        )
        return

    user_ids_total = len(context.bot_data["db"].get_all_user_ids())
    if not user_ids_total:
        await update.message.reply_text("No users in database yet.")
        return

    status = await update.message.reply_text(
        f"📢 Broadcasting to {user_ids_total} user(s)..."
    )
    sent, failed, _ = await _run_broadcast(context, text)
    await status.edit_text(
        f"📢 Broadcast complete.\nSent: {sent}\nFailed: {failed}"
    )


async def show_stock(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not _is_admin(update, context):
        return
    db: Database = context.bot_data["db"]
    await update.message.reply_text(f"📦 Available proxies: {db.count_available_proxies()}")


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
            f"Pack: {order['pack_name']} ({order['proxy_count']} proxies)\n"
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


async def add_proxies_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not _is_admin(update, context):
        return

    text = ""
    if update.message.reply_to_message and update.message.reply_to_message.text:
        text = update.message.reply_to_message.text
    elif context.args:
        text = " ".join(context.args)

    if not text:
        context.user_data[WAITING_ADMIN_PROXIES] = True
        await update.message.reply_text(
            "➕ <b>Add Proxies</b>\n\n"
            "Send a proxy list (one per line) or upload a <code>.txt</code> file.\n\n"
            "You can also reply to a proxy message with <code>/add_proxies</code>.",
            parse_mode="HTML",
            reply_markup=ADMIN_CANCEL_KEYBOARD,
        )
        return

    await _add_proxies_from_text(update, context, text)


async def _add_proxies_from_text(
    update: Update, context: ContextTypes.DEFAULT_TYPE, text: str
) -> None:
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    db: Database = context.bot_data["db"]
    added = db.add_proxies(lines)
    clear_admin_modes(context)

    msg = update.effective_message
    if msg:
        await msg.reply_text(
            f"✅ Added {added} proxy(s).\n"
            f"Total stock: {db.count_available_proxies()}"
        )


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
        label = "Broadcast" if action == "broadcast" else "Notice"
        await query.message.reply_text(
            f"📢 <b>{label} Mode</b>\n\n"
            "Send the message you want to deliver to all users.",
            parse_mode="HTML",
            reply_markup=ADMIN_CANCEL_KEYBOARD,
        )
        return

    if action == "stock":
        db: Database = context.bot_data["db"]
        await query.message.reply_text(
            f"📦 Available proxies: {db.count_available_proxies()}"
        )
        return

    if action == "pending":
        await _send_pending_orders(update, context)
        return

    if action == "add_proxies":
        clear_admin_modes(context)
        context.user_data[WAITING_ADMIN_PROXIES] = True
        await query.message.reply_text(
            "➕ <b>Add Proxies</b>\n\n"
            "Send a proxy list (one per line) or upload a <code>.txt</code> file.",
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

    clear_admin_modes(context)
    user_ids_total = len(context.bot_data["db"].get_all_user_ids())
    if not user_ids_total:
        await update.message.reply_text("No users in database yet.")
        return

    status = await update.message.reply_text(
        f"📢 Broadcasting to {user_ids_total} user(s)..."
    )
    sent, failed, _ = await _run_broadcast(context, text)
    await status.edit_text(
        f"📢 Broadcast complete.\nSent: {sent}\nFailed: {failed}"
    )


async def receive_admin_proxies(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not _is_admin(update, context):
        return
    if not context.user_data.get(WAITING_ADMIN_PROXIES):
        return

    text = ""
    if update.message.document:
        doc = update.message.document
        if doc.file_size and doc.file_size > 512_000:
            await update.message.reply_text("File too large. Max size is 512 KB.")
            return
        file = await context.bot.get_file(doc.file_id)
        data = await file.download_as_bytearray()
        text = data.decode("utf-8", errors="ignore")
    elif update.message.text:
        text = update.message.text
        if is_menu_button(text):
            clear_admin_modes(context)
            return
    else:
        return

    await _add_proxies_from_text(update, context, text)


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
            proxy_block = "\n".join(proxies)
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
    application.add_handler(CommandHandler("broadcast", broadcast_notice))
    application.add_handler(CommandHandler("notice", broadcast_notice))
    application.add_handler(CommandHandler("stock", show_stock))
    application.add_handler(CommandHandler("pending", show_pending))
    application.add_handler(CommandHandler("add_proxies", add_proxies_command))
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
