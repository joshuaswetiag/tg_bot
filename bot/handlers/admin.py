from telegram import Update
from telegram.ext import CallbackQueryHandler, CommandHandler, ContextTypes, MessageHandler, filters

from bot.database import Database


def _is_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    user = update.effective_user
    if not user:
        return False
    return user.id in context.bot_data["settings"].admin_ids


async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not _is_admin(update, context):
        return

    db: Database = context.bot_data["db"]
    maintenance = db.is_maintenance()
    stock = db.count_available_proxies()
    pending = len(db.get_pending_orders())

    await update.message.reply_text(
        "🛠 **Admin Panel**\n\n"
        f"Maintenance: {'ON' if maintenance else 'OFF'}\n"
        f"Proxy stock: {stock}\n"
        f"Pending orders: {pending}\n\n"
        "**Commands:**\n"
        "`/maintenance_on` — Enable maintenance\n"
        "`/maintenance_off` — Disable maintenance\n"
        "`/add_proxies` — Reply to a message with proxy list\n"
        "`/stock` — Show available stock\n"
        "`/pending` — List pending orders",
        parse_mode="Markdown",
    )


async def maintenance_on(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not _is_admin(update, context):
        return
    db: Database = context.bot_data["db"]
    db.set_maintenance(True)
    await update.message.reply_text("⚠️ Maintenance mode enabled.")


async def maintenance_off(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not _is_admin(update, context):
        return
    db: Database = context.bot_data["db"]
    db.set_maintenance(False)
    await update.message.reply_text("🎉 Maintenance mode disabled. Bot is back online!")


async def show_stock(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not _is_admin(update, context):
        return
    db: Database = context.bot_data["db"]
    await update.message.reply_text(f"📦 Available proxies: {db.count_available_proxies()}")


async def show_pending(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not _is_admin(update, context):
        return
    db: Database = context.bot_data["db"]
    orders = db.get_pending_orders()
    if not orders:
        await update.message.reply_text("No pending orders.")
        return

    from bot.keyboards import order_admin_keyboard

    for order in orders:
        text = (
            f"Order #{order['id']}\n"
            f"User: {order['first_name']} (@{order['username'] or 'n/a'}) `{order['user_id']}`\n"
            f"Pack: {order['pack_name']} ({order['proxy_count']} proxies)\n"
            f"Amount: ৳{order['amount']:.1f}\n"
            f"TRX: `{order['trx_id']}`"
        )
        await update.message.reply_text(
            text,
            parse_mode="Markdown",
            reply_markup=order_admin_keyboard(order["id"]),
        )


async def add_proxies_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not _is_admin(update, context):
        return

    text = ""
    if update.message.reply_to_message and update.message.reply_to_message.text:
        text = update.message.reply_to_message.text
    elif context.args:
        text = " ".join(context.args)

    if not text:
        await update.message.reply_text(
            "Reply to a message containing proxies (one per line), or:\n"
            "`/add_proxies host:port`",
            parse_mode="Markdown",
        )
        return

    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    db: Database = context.bot_data["db"]
    added = db.add_proxies(lines)
    await update.message.reply_text(f"Added {added} proxy(s). Total stock: {db.count_available_proxies()}")


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
                await context.bot.send_message(
                    order["user_id"],
                    f"✅ **Order #{order_id} completed!**\n\n"
                    f"Your {order['proxy_count']} proxies:\n\n"
                    f"```\n{proxy_block}\n```",
                    parse_mode="Markdown",
                )
            except Exception:
                pass
        else:
            await query.edit_message_text("Could not approve (already processed?).")


def register_admin_handlers(application) -> None:
    application.add_handler(CommandHandler("admin", admin_panel))
    application.add_handler(CommandHandler("maintenance_on", maintenance_on))
    application.add_handler(CommandHandler("maintenance_off", maintenance_off))
    application.add_handler(CommandHandler("stock", show_stock))
    application.add_handler(CommandHandler("pending", show_pending))
    application.add_handler(CommandHandler("add_proxies", add_proxies_command))
    application.add_handler(CallbackQueryHandler(admin_order_action, pattern=r"^admin:"))
