import re
from io import BytesIO

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def normalize_account_line(line: str) -> str | None:
    line = line.strip()
    if not line or line.startswith("#"):
        return None
    if ":" not in line:
        return None
    email, password = line.split(":", 1)
    email = email.strip()
    password = password.strip()
    if not email or not password or not _EMAIL_RE.match(email):
        return None
    return f"{email}:{password}"


def parse_accounts_from_text(text: str) -> list[str]:
    seen: set[str] = set()
    accounts: list[str] = []
    for line in text.splitlines():
        normalized = normalize_account_line(line)
        if normalized and normalized not in seen:
            seen.add(normalized)
            accounts.append(normalized)
    return accounts


def parse_accounts_from_excel(data: bytes) -> list[str]:
    from openpyxl import load_workbook

    wb = load_workbook(BytesIO(data), read_only=True, data_only=True)
    try:
        ws = wb.active
        if ws is None:
            return []

        seen: set[str] = set()
        accounts: list[str] = []
        for row in ws.iter_rows(min_row=1, values_only=True):
            if not row or len(row) < 3:
                continue
            email_raw = row[1]
            password_raw = row[2]
            if email_raw is None or password_raw is None:
                continue
            email = str(email_raw).strip()
            password = str(password_raw).strip()
            if not email or not password:
                continue
            normalized = normalize_account_line(f"{email}:{password}")
            if normalized and normalized not in seen:
                seen.add(normalized)
                accounts.append(normalized)
        return accounts
    finally:
        wb.close()


def parse_accounts_upload(filename: str, data: bytes) -> list[str]:
    lower = filename.lower()
    if lower.endswith((".xlsx", ".xlsm")):
        return parse_accounts_from_excel(data)
    return parse_accounts_from_text(data.decode("utf-8", errors="ignore"))


def format_accounts_delivery_file(account_lines: list[str]) -> str:
    blocks: list[str] = []
    for line in account_lines:
        normalized = normalize_account_line(line)
        if not normalized:
            continue
        email, password = normalized.split(":", 1)
        blocks.append(f"Email: {email}\nPassword: {password}")
    return "\n\n".join(blocks) + ("\n" if blocks else "")


def account_count_label(count: int) -> str:
    return f"{count} proxy account{'s' if count != 1 else ''}"
