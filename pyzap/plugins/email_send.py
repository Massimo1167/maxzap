"""Send a simple email message."""

from __future__ import annotations

import smtplib
from email.message import EmailMessage
from typing import Any, Dict

from ..core import BaseAction


class EmailSendAction(BaseAction):
    """Send email using the local SMTP server."""

    def execute(self, data: Dict[str, Any]) -> None:
        to_addr = self.params.get("to") or data.get("to")
        subject = self.params.get("subject", "PyZap Notification")
        body = data.get("text") or data.get("body") or ""
        from_addr = self.params.get("from_addr", "noreply@example.com")
        host = self.params.get("host", "localhost")
        port = int(self.params.get("port", 25))
        if not to_addr:
            raise ValueError("recipient address required")
        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = from_addr
        msg["To"] = to_addr
        msg.set_content(body)
        with smtplib.SMTP(host, port) as smtp:
            smtp.send_message(msg)
