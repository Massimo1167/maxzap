"""IMAP polling trigger implementation."""

from __future__ import annotations

import email
import imaplib
import logging
from typing import Any, Dict, List

from ..core import BaseTrigger


class ImapPollTrigger(BaseTrigger):
    """Poll an IMAP server for new messages."""

    def poll(self) -> List[Dict[str, Any]]:
        """Return messages from the configured IMAP server.

        Expected configuration keys:
        - ``host``: IMAP server hostname.
        - ``username`` and ``password``: login credentials.
        - ``port`` (optional): IMAP SSL port, defaults to ``993``.
        - ``mailbox`` (optional): mailbox to select, defaults to ``INBOX``.
        - ``search`` (optional): IMAP search query, defaults to ``UNSEEN``.
        """

        host = self.config.get("host")
        username = self.config.get("username")
        password = self.config.get("password")
        mailbox = self.config.get("mailbox", "INBOX")
        search = self.config.get("search", "UNSEEN")
        try:
            port = int(self.config.get("port", 993))
        except Exception:
            port = 993

        logging.info(
            "Polling IMAP %s mailbox %s with search '%s'",
            host,
            mailbox,
            search,
        )

        if not host or not username or not password:
            logging.error("IMAP configuration incomplete")
            return []

        try:
            with imaplib.IMAP4_SSL(host, port) as client:
                client.login(username, password)

                logging.info("Logged in to %s as %s", host, username)
                client.select(mailbox)
                status, data = client.search(None, search)
                if status != "OK":
                    logging.error("IMAP search failed: %s", status)
                    return []
                logging.info("IMAP search returned %d messages", len(data[0].split()))
                messages = []
                for num in data[0].split():
                    status, msg_data = client.fetch(num, "(RFC822)")
                    if status != "OK" or not msg_data:
                        continue
                    msg = email.message_from_bytes(msg_data[0][1])
                    payload = {
                        "id": num.decode(),
                        "subject": msg.get("Subject", ""),
                        "from": msg.get("From", ""),
                        "body": msg.get_payload(decode=True).decode(errors="replace"),
                    }
                    messages.append(payload)

                    logging.debug("Fetched IMAP message %s", num.decode())
                logging.info("IMAP polling returned %d messages", len(messages))
                return messages
        except Exception as exc:  # pylint: disable=broad-except
            logging.exception("IMAP polling failed: %s", exc)
            return []
