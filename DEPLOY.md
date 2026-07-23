# Proxy Store Bot — 24/7 Deploy Guide

## What you need ready

1. **Bot token** from [@BotFather](https://t.me/BotFather)
2. **Your Telegram ID** from [@userinfobot](https://t.me/userinfobot)
3. **Supabase account** (you already have one)
4. **GitHub account** + **Railway account** ([railway.app](https://railway.app))

---

## Part 1 — Supabase (database)

### 1. Create or pick a project

- Go to [supabase.com/dashboard](https://supabase.com/dashboard)
- **New project** → name it `proxy-store-bot` → region **Singapore** (closest to BD)
- Wait ~2 minutes for it to finish provisioning

### 2. Run the database schema

- Open your project → **SQL Editor** → **New query**
- Copy all of `supabase/schema.sql` and click **Run**
- You should see “Success”

### 3. Get DATABASE_URL

- **Project Settings** → **Database** → **Connection string** → **URI**
- Copy the URI and replace `[YOUR-PASSWORD]` with your database password

Example:
```
postgresql://postgres.xxxx:YOUR_PASSWORD@aws-0-ap-southeast-1.pooler.supabase.com:6543/postgres
```

### 4. (Optional) Apply schema from terminal

```powershell
cd h:\tg_bot
$env:DATABASE_URL = "postgresql://postgres...."
python scripts/apply_schema.py
```

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
