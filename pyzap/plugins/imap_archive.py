"""IMAP archive action."""

from __future__ import annotations

import email
import imaplib
import os
from pathlib import Path
from typing import Any, Dict, List

from ..core import BaseAction
from .gdrive_upload import GDriveUploadAction


class ImapArchiveAction(BaseAction):
    """Download an IMAP message and attachments and store them."""

    def _fetch_message(self, msg_id: str, host: str, username: str, password: str, mailbox: str) -> email.message.EmailMessage:
        with imaplib.IMAP4_SSL(host) as client:
            client.login(username, password)
            client.select(mailbox)
            status, data = client.fetch(msg_id, "(RFC822)")
            if status != "OK" or not data:
                raise RuntimeError("IMAP fetch failed")
            return email.message_from_bytes(data[0][1])  # type: ignore[arg-type]

    def execute(self, data: Dict[str, Any]) -> Dict[str, Any]:
        host = self.params.get("host")
        username = self.params.get("username")
        password = self.params.get("password")
        mailbox = self.params.get("mailbox", "INBOX")
        drive_parent = self.params.get("drive_folder_id")
        local_dir = self.params.get("local_dir")
        token = self.params.get("token") or os.environ.get("GDRIVE_TOKEN")
        save_attachments = bool(self.params.get("save_attachments", True))
        msg_id = data.get("id")
        if not host or not username or not password:
            raise ValueError("IMAP credentials missing")
        if not msg_id:
            raise ValueError("Message id required")
        if not local_dir and not drive_parent:
            raise ValueError("Either local_dir or drive_folder_id must be set")

        msg = self._fetch_message(msg_id, host, username, password, mailbox)
        sender = msg.get("From", "")
        subject = msg.get("Subject", "")
        date = msg.get("Date", "")
        snippet = msg.get_payload(decode=True).decode(errors="replace") if msg.get_payload(decode=True) else ""

        attachments: List[str] = []
        files: List[tuple[str, bytes]] = []
        if save_attachments:
            for part in msg.walk():
                if part.get_content_disposition() == "attachment":
                    filename = part.get_filename() or "attachment"
                    payload = part.get_payload(decode=True) or b""
                    files.append((filename, payload))
                    attachments.append(filename)

        folder_name = str(msg_id)
        storage_path = ""
        if local_dir:
            folder = Path(local_dir) / folder_name
            folder.mkdir(parents=True, exist_ok=True)
            with open(folder / "message.txt", "w", encoding="utf-8") as fh:
                fh.write(snippet)
            for name, content in files:
                with open(folder / name, "wb") as fh:
                    fh.write(content)
            storage_path = str(folder)
        else:
            if not token:
                raise ValueError("token required for Google Drive upload")
            from .gmail_archive import GmailArchiveAction  # for helper

            action = GmailArchiveAction({"folder_id": drive_parent, "token": token})
            # create folder via helper
            folder_id = action._create_drive_folder(folder_name, drive_parent, token)  # type: ignore[attr-defined]
            uploader = GDriveUploadAction({"folder_id": folder_id, "token": token})
            uploader.execute({"content": snippet.encode(), "filename": "message.txt"})
            for name, content in files:
                uploader.execute({"content": content, "filename": name})
            storage_path = folder_id

        return {
            "datetime": date,
            "sender": sender,
            "subject": subject,
            "summary": snippet,
            "attachments": attachments,
            "storage_path": storage_path,
        }
