"""SMTP delivery for generated markdown briefs."""

from __future__ import annotations

import argparse
import os
import smtplib
from dataclasses import dataclass
from email.message import EmailMessage
from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - only used before dependencies are installed
    def load_dotenv() -> bool:
        return False


@dataclass(frozen=True)
class SMTPConfig:
    host: str
    port: int
    user: str
    password: str
    email_to: str
    email_from: str
    use_tls: bool = True
    use_ssl: bool = False
    subject_prefix: str = "[John Commentary Scan]"


def env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def load_smtp_config() -> SMTPConfig:
    load_dotenv()

    required = {
        "EMAIL_HOST": os.getenv("EMAIL_HOST"),
        "EMAIL_PORT": os.getenv("EMAIL_PORT"),
        "EMAIL_USER": os.getenv("EMAIL_USER"),
        "EMAIL_PASSWORD": os.getenv("EMAIL_PASSWORD"),
        "EMAIL_TO": os.getenv("EMAIL_TO"),
        "EMAIL_FROM": os.getenv("EMAIL_FROM"),
    }
    missing = [name for name, value in required.items() if not value]
    if missing:
        raise RuntimeError(f"Missing email environment variables: {', '.join(missing)}")

    return SMTPConfig(
        host=required["EMAIL_HOST"] or "",
        port=int(required["EMAIL_PORT"] or "587"),
        user=required["EMAIL_USER"] or "",
        password=required["EMAIL_PASSWORD"] or "",
        email_to=required["EMAIL_TO"] or "",
        email_from=required["EMAIL_FROM"] or "",
        use_tls=env_bool("EMAIL_USE_TLS", True),
        use_ssl=env_bool("EMAIL_USE_SSL", False),
        subject_prefix=os.getenv("EMAIL_SUBJECT_PREFIX", "[John Commentary Scan]"),
    )


def send_brief_email(subject: str, markdown_body: str, config: SMTPConfig | None = None) -> None:
    cfg = config or load_smtp_config()
    message = EmailMessage()
    message["Subject"] = f"{cfg.subject_prefix} {subject}".strip()
    message["From"] = cfg.email_from
    message["To"] = cfg.email_to
    message.set_content(markdown_body)

    if cfg.use_ssl:
        with smtplib.SMTP_SSL(cfg.host, cfg.port) as smtp:
            smtp.login(cfg.user, cfg.password)
            smtp.send_message(message)
        return

    with smtplib.SMTP(cfg.host, cfg.port) as smtp:
        if cfg.use_tls:
            smtp.starttls()
        smtp.login(cfg.user, cfg.password)
        smtp.send_message(message)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Email a generated commentary brief.")
    parser.add_argument("brief_path", help="Path to the markdown brief.")
    parser.add_argument("--subject", default="Commentary brief")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    body = Path(args.brief_path).read_text(encoding="utf-8")
    send_brief_email(args.subject, body)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
