# Proxy Store Bot — 24/7 Deploy Guide

> **Your Supabase project is ready:** [proxy-store-bot dashboard](https://supabase.com/dashboard/project/yrmpstkasqmwrndqlifj)  
> Database tables are already created. Credentials are in `SETUP_CREDENTIALS.local.txt` (local only).

## What you need ready

1. **Bot token** from [@BotFather](https://t.me/BotFather) — see **Step 0** below
2. **Your Telegram ID** from [@userinfobot](https://t.me/userinfobot)
3. **GitHub account** + **Railway account** ([railway.app](https://railway.app))

---

## Step 0 — Create your Telegram bot (2 min)

1. Open Telegram → search **@BotFather**
2. Send `/newbot`
3. Choose a **display name** (e.g. `My Proxy Store`)
4. Choose a **username** ending in `bot` (e.g. `myproxystore_bot`)
5. Copy the **token** BotFather gives you
6. Edit `h:\tg_bot\.env`:
   ```
   BOT_TOKEN=paste_token_here
   ADMIN_IDS=your_numeric_id
   ```

7. Test locally:
   ```powershell
   cd h:\tg_bot
   pip install -r requirements.txt
   python run.py
   ```
8. Message your bot → `/start`

---

## Part 1 — Supabase (database) ✅ DONE

Your project **proxy-store-bot** (Singapore) is created and schema is applied.

- Dashboard: https://supabase.com/dashboard/project/yrmpstkasqmwrndqlifj
- `DATABASE_URL` is already in your `.env` file

To view data: Supabase → **Table Editor** → `proxy_stock`, `orders`, `users`

---

## Part 2 — GitHub (code hosting)

```powershell
cd h:\tg_bot
git init
git add .
git commit -m "Proxy store Telegram bot with Supabase + Railway"

# Create repo on github.com → New repository → name: tg-bot
git remote add origin https://github.com/YOUR_USERNAME/tg-bot.git
git branch -M main
git push -u origin main
```

---

## Part 3 — Railway (24/7 bot)

1. Go to [railway.app](https://railway.app) → **New Project**
2. **Deploy from GitHub repo** → select `tg-bot`
3. Click the service → **Variables** → add:

| Variable | Value |
|----------|--------|
| `BOT_TOKEN` | Your BotFather token |
| `ADMIN_IDS` | Your Telegram numeric ID |
| `DATABASE_URL` | Supabase URI from Part 1 |
| `BKASH_NUMBER` | Your bKash number |
| `BKASH_TYPE` | Personal |
| `BOT_NAME` | Proxy Store |
| `REQUIRED_CHANNEL` | `@your_channel` or leave empty |

4. Railway auto-runs `python run.py` — check **Deployments → Logs** for:
   ```
   Starting Proxy Store — database: Supabase/PostgreSQL
   ```

5. Open Telegram → message your bot → `/start`

---

## Part 4 — Load proxy stock

Message your bot as admin:

```
/add_proxies
```

Reply to that with proxies (one per line):
```
103.45.12.1:8080
user:pass@103.45.12.2:3128
```

Check stock: `/stock`

---

## Local test (before Railway)

```powershell
cd h:\tg_bot
copy .env.example .env
# Edit .env — set BOT_TOKEN, ADMIN_IDS, DATABASE_URL
pip install -r requirements.txt
python run.py
```

Leave `DATABASE_URL` empty in `.env` to use local SQLite instead.

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| `Could not connect to PostgreSQL` | Run `supabase/schema.sql` in SQL Editor |
| Bot not responding on Railway | Check Deployments → Logs for errors |
| `BOT_TOKEN is required` | Add `BOT_TOKEN` in Railway Variables |
| Duplicate TRX ID | Working as intended — prevents double payment |

---

## Cost

- **Supabase**: Free tier (500 MB DB — enough for thousands of proxies)
- **Railway**: ~$5/month after trial credit (keeps bot online 24/7)
