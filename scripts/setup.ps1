param(
    [string]$BotToken = "",
    [string]$AdminId = "",
    [string]$DatabaseUrl = "",
    [string]$BkashNumber = "01845007133"
)

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot\..

Write-Host "=== Proxy Store Bot — Setup ===" -ForegroundColor Cyan

# 1. Python deps
Write-Host "`n[1/4] Installing Python dependencies..."
python -m pip install -r requirements.txt -q

# 2. .env file
Write-Host "[2/4] Creating .env file..."
if (-not (Test-Path .env)) {
    Copy-Item .env.example .env
}

function Set-EnvVar($name, $value) {
    if (-not $value) { return }
    $content = Get-Content .env -Raw
    $pattern = "(?m)^$name=.*$"
    if ($content -match $pattern) {
        $content = $content -replace $pattern, "$name=$value"
    } else {
        $content += "`n$name=$value"
    }
    Set-Content .env $content.TrimEnd()
}

if ($BotToken)   { Set-EnvVar "BOT_TOKEN" $BotToken }
if ($AdminId)    { Set-EnvVar "ADMIN_IDS" $AdminId }
if ($DatabaseUrl){ Set-EnvVar "DATABASE_URL" $DatabaseUrl }
if ($BkashNumber){ Set-EnvVar "BKASH_NUMBER" $BkashNumber }

# 3. Apply Supabase schema if DATABASE_URL set
Write-Host "[3/4] Database setup..."
$dbUrl = $DatabaseUrl
if (-not $dbUrl -and (Test-Path .env)) {
    $line = Get-Content .env | Where-Object { $_ -match "^DATABASE_URL=" }
    if ($line) { $dbUrl = ($line -split "=", 2)[1].Trim() }
}

if ($dbUrl -and $dbUrl -notmatch "YOUR_PASSWORD|xxxx") {
    $env:DATABASE_URL = $dbUrl
    python scripts/apply_schema.py
    Write-Host "Supabase schema applied." -ForegroundColor Green
} else {
    Write-Host "Skip schema: set DATABASE_URL in .env or pass -DatabaseUrl" -ForegroundColor Yellow
    Write-Host "Or run supabase/schema.sql manually in Supabase SQL Editor."
}

# 4. Git init
Write-Host "[4/4] Git repository..."
if (-not (Test-Path .git)) {
    git init | Out-Null
    git add -A
    git commit -m "Proxy store Telegram bot — Supabase + Railway ready" | Out-Null
    Write-Host "Git repo initialized with first commit." -ForegroundColor Green
} else {
    Write-Host "Git repo already exists."
}

Write-Host "`n=== Next steps ===" -ForegroundColor Cyan
Write-Host "1. Edit .env with BOT_TOKEN, ADMIN_IDS, DATABASE_URL"
Write-Host "2. Test locally:  python run.py"
Write-Host "3. Push to GitHub and deploy on Railway — see DEPLOY.md"
Write-Host ""
