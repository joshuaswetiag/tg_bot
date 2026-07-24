import csv
from io import StringIO
from typing import Any


def format_store_stats_message(stats: dict[str, Any]) -> str:
    return (
        "<b>📊 Store Statistics</b>\n\n"
        f"👥 Total users: <b>{stats['total_users']}</b>\n"
        f"📋 Total orders: <b>{stats['total_orders']}</b>\n"
        f"⏳ Pending: <b>{stats['pending_orders']}</b>\n"
        f"✅ Completed: <b>{stats['completed_orders']}</b>\n"
        f"📦 Accounts sold: <b>{stats['accounts_sold']}</b>\n"
        f"💵 Revenue (completed): <b>৳{stats['revenue_bdt']:.1f}</b>"
    )


def export_orders_csv(orders: list[dict[str, Any]]) -> str:
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(
        [
            "order_id",
            "user_id",
            "username",
            "first_name",
            "pack_name",
            "proxy_count",
            "amount_bdt",
            "status",
            "trx_id",
            "created_at",
        ]
    )
    for o in orders:
        writer.writerow(
            [
                o.get("id"),
                o.get("user_id"),
                o.get("username") or "",
                o.get("first_name") or "",
                o.get("pack_name"),
                o.get("proxy_count"),
                o.get("amount"),
                o.get("status"),
                o.get("trx_id") or "",
                o.get("created_at"),
            ]
        )
    return output.getvalue()


def export_users_csv(users: list[dict[str, Any]]) -> str:
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(
        [
            "user_id",
            "username",
            "first_name",
            "joined_at",
            "total_orders",
            "completed_orders",
            "accounts_bought",
            "spent_bdt",
        ]
    )
    for u in users:
        writer.writerow(
            [
                u.get("user_id"),
                u.get("username") or "",
                u.get("first_name") or "",
                u.get("created_at"),
                u.get("total_orders"),
                u.get("completed_orders"),
                u.get("accounts_bought"),
                u.get("spent_bdt"),
            ]
        )
    return output.getvalue()


def format_order_summary_lines(orders: list[dict[str, Any]], limit: int = 15) -> str:
    lines = ["<b>📋 Recent Orders</b>\n"]
    for o in orders[:limit]:
        user = o.get("first_name") or "User"
        uname = f"@{o['username']}" if o.get("username") else f"id `{o['user_id']}`"
        lines.append(
            f"<b>#{o['id']}</b> {user} ({uname})\n"
            f"{o.get('pack_name')} · {o.get('proxy_count')} acct · "
            f"৳{float(o.get('amount', 0)):.0f} · {o.get('status')}"
        )
    if len(orders) > limit:
        lines.append(f"\n… and {len(orders) - limit} more in export file.")
    return "\n".join(lines)
