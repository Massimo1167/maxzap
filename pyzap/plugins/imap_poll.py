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
        - ``max_results`` (optional): maximum number of messages to return,
          defaults to ``100``.
        - ``has_attachment`` (optional): filter messages by presence of
          attachments. Accepts ``1``, ``true`` or ``yes`` to keep only messages
          with attachments, and ``0``, ``false`` or ``no`` to keep only those
          without.
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
        try:
            max_results = int(self.config.get("max_results", 100))
        except Exception:
            max_results = 100
        truthy = {"1", "true", "yes"}
        falsy = {"0", "false", "no"}
        has_attachment_cfg = self.config.get("has_attachment")
        has_attachment_filter = None
        if has_attachment_cfg is not None:
            lower = str(has_attachment_cfg).lower()
            if lower in truthy:
                has_attachment_filter = True
            elif lower in falsy:
                has_attachment_filter = False

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
                for num in data[0].split()[:max_results]:
                    status, msg_data = client.fetch(num, "(RFC822)")
                    if status != "OK" or not msg_data:
                        continue
                    msg = email.message_from_bytes(msg_data[0][1])
                    if msg.is_multipart():
                        body = ""
                        has_attachments = False
                        # Identify attachments via content disposition
                        # (inline with filename is also treated as attachment)
                        for part in msg.walk():
                            cd = part.get_content_disposition()
                            filename = part.get_filename() or part.get_param("name")
                            is_attachment = bool(
                                filename
                                and (cd in ("attachment", "inline") or cd is None)
                            )
                            if (
                                part.get_content_type() == "text/plain"
                                and not body
                                and not is_attachment
                            ):
                                payload_bytes = part.get_payload(decode=True)
                                if payload_bytes is not None:
                                    body = payload_bytes.decode(errors="replace")
                            elif is_attachment:
                                has_attachments = True
                    else:
                        payload_bytes = msg.get_payload(decode=True)
                        # Apply the same attachment detection for single-part messages
                        cd = msg.get_content_disposition()
                        filename = msg.get_filename() or msg.get_param("name")
                        is_attachment = bool(
                            filename
                            and (cd in ("attachment", "inline") or cd is None)
                        )
                        if msg.get_content_type() == "text/plain" and not is_attachment:
                            body = (
                                payload_bytes.decode(errors="replace")
                                if payload_bytes is not None
                                else ""
                            )
                        else:
                            body = ""
                        has_attachments = is_attachment

                    if (
                        has_attachment_filter is not None
                        and has_attachments != has_attachment_filter
                    ):
                        continue

                    payload = {
                        "id": num.decode(),
                        "subject": msg.get("Subject", ""),
                        "from": msg.get("From", ""),
                        "body": body,
                    }
                    messages.append(payload)

                    logging.debug("Fetched IMAP message %s", num.decode())
                logging.info("IMAP polling returned %d messages", len(messages))
                return messages
        except Exception as exc:  # pylint: disable=broad-except
            logging.exception("IMAP polling failed: %s", exc)
            return []
