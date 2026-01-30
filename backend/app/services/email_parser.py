"""Email parser — converts raw IMAP messages into structured data."""

import email
import re
from datetime import datetime, timezone
from email import policy
from email.headerregistry import Address
from email.utils import parsedate_to_datetime
from typing import Optional
from dataclasses import dataclass, field

from bs4 import BeautifulSoup


@dataclass
class ParsedEmail:
    """Structured representation of a parsed email."""
    message_id: str
    subject: Optional[str] = None
    from_address: Optional[str] = None
    from_name: Optional[str] = None
    to_addresses: list[dict] = field(default_factory=list)
    cc_addresses: list[dict] = field(default_factory=list)
    reply_to: Optional[str] = None
    body_text: Optional[str] = None
    body_html: Optional[str] = None
    date_sent: Optional[datetime] = None
    is_read: bool = False
    has_attachments: bool = False
    size_bytes: int = 0
    raw_headers: dict = field(default_factory=dict)
    links: list[str] = field(default_factory=list)


def parse_address(addr_str: str) -> list[dict]:
    """Parse an address header into a list of {name, address} dicts."""
    if not addr_str:
        return []

    results = []
    try:
        # Use email.headerregistry for robust parsing
        msg = email.message_from_string(f"To: {addr_str}", policy=policy.default)
        header = msg["To"]
        if hasattr(header, "addresses"):
            for addr in header.addresses:
                results.append({
                    "name": str(addr.display_name) if addr.display_name else None,
                    "address": f"{addr.username}@{addr.domain}" if addr.domain else str(addr),
                })
    except Exception:
        # Fallback: simple regex
        email_pattern = re.compile(r'[\w.+-]+@[\w-]+\.[\w.-]+')
        for match in email_pattern.finditer(addr_str):
            results.append({"name": None, "address": match.group()})

    return results


def extract_body(msg: email.message.Message) -> tuple[Optional[str], Optional[str]]:
    """Extract text and HTML body from a MIME message."""
    text_body = None
    html_body = None

    if msg.is_multipart():
        for part in msg.walk():
            content_type = part.get_content_type()
            disposition = str(part.get("Content-Disposition", ""))

            if "attachment" in disposition:
                continue

            try:
                payload = part.get_payload(decode=True)
                if payload is None:
                    continue
                charset = part.get_content_charset() or "utf-8"
                decoded = payload.decode(charset, errors="replace")
            except Exception:
                continue

            if content_type == "text/plain" and text_body is None:
                text_body = decoded
            elif content_type == "text/html" and html_body is None:
                html_body = decoded
    else:
        content_type = msg.get_content_type()
        try:
            payload = msg.get_payload(decode=True)
            if payload:
                charset = msg.get_content_charset() or "utf-8"
                decoded = payload.decode(charset, errors="replace")
                if content_type == "text/plain":
                    text_body = decoded
                elif content_type == "text/html":
                    html_body = decoded
        except Exception:
            pass

    # If we only have HTML, generate a text version
    if html_body and not text_body:
        soup = BeautifulSoup(html_body, "lxml")
        text_body = soup.get_text(separator="\n", strip=True)

    return text_body, html_body


def extract_links(html: Optional[str], text: Optional[str]) -> list[str]:
    """Extract unique URLs from email content."""
    urls = set()

    # Extract from HTML
    if html:
        soup = BeautifulSoup(html, "lxml")
        for a_tag in soup.find_all("a", href=True):
            href = a_tag["href"].strip()
            if href and href.startswith(("http://", "https://")):
                # Skip common non-content URLs
                if not _is_junk_url(href):
                    urls.add(href)

    # Extract from text body
    if text:
        url_pattern = re.compile(
            r'https?://[^\s<>"\')\]]+',
            re.IGNORECASE
        )
        for match in url_pattern.finditer(text):
            url = match.group().rstrip(".,;:!?)")
            if not _is_junk_url(url):
                urls.add(url)

    return sorted(urls)


def _is_junk_url(url: str) -> bool:
    """Filter out tracking pixels, unsubscribe links, and other noise."""
    junk_patterns = [
        "unsubscribe",
        "list-unsubscribe",
        "manage-preferences",
        "email-preferences",
        "tracking",
        "click.mailchimp",
        "click.convertkit",
        "click.pstmrk",
        "email.mg.",
        "mandrillapp.com",
        "sendgrid.net/wf/click",
        "list-manage.com/track",
        "open.substack.com/pub",
        # Common image/pixel patterns
        ".gif?",
        ".png?u=",
        "beacon.",
        "pixel.",
        "/track/open",
        "/o/",  # common open tracking
    ]
    url_lower = url.lower()
    return any(p in url_lower for p in junk_patterns)


def has_attachments(msg: email.message.Message) -> bool:
    """Check if email has non-inline attachments."""
    if not msg.is_multipart():
        return False
    for part in msg.walk():
        disposition = str(part.get("Content-Disposition", ""))
        if "attachment" in disposition:
            return True
    return False


def parse_raw_email(raw_bytes: bytes, uid: Optional[int] = None, folder: str = "INBOX", flags: tuple = ()) -> ParsedEmail:
    """Parse raw email bytes into a structured ParsedEmail."""
    msg = email.message_from_bytes(raw_bytes, policy=policy.default)

    # Extract Message-ID
    message_id = msg.get("Message-ID", "")
    if not message_id:
        # Generate a fallback ID
        message_id = f"<no-id-uid-{uid}@local>"

    # Parse from address
    from_header = msg.get("From", "")
    from_addrs = parse_address(from_header)
    from_address = from_addrs[0]["address"] if from_addrs else None
    from_name = from_addrs[0].get("name") if from_addrs else None

    # Parse date
    date_sent = None
    date_header = msg.get("Date")
    if date_header:
        try:
            date_sent = parsedate_to_datetime(str(date_header))
            if date_sent.tzinfo is None:
                date_sent = date_sent.replace(tzinfo=timezone.utc)
        except Exception:
            pass

    # Extract body
    body_text, body_html = extract_body(msg)

    # Extract links
    links = extract_links(body_html, body_text)

    # Build raw headers dict (select important ones)
    important_headers = [
        "From", "To", "Cc", "Subject", "Date", "Reply-To",
        "List-Unsubscribe", "X-Mailer", "DKIM-Signature",
    ]
    raw_headers = {}
    for h in important_headers:
        val = msg.get(h)
        if val:
            raw_headers[h] = str(val)

    # Check flags
    is_read = b"\\Seen" in flags if flags else False

    return ParsedEmail(
        message_id=str(message_id).strip(),
        subject=str(msg.get("Subject", "")) or None,
        from_address=from_address,
        from_name=from_name,
        to_addresses=parse_address(msg.get("To", "")),
        cc_addresses=parse_address(msg.get("Cc", "")),
        reply_to=msg.get("Reply-To"),
        body_text=body_text,
        body_html=body_html,
        date_sent=date_sent,
        is_read=is_read,
        has_attachments=has_attachments(msg),
        size_bytes=len(raw_bytes),
        raw_headers=raw_headers,
        links=links,
    )
