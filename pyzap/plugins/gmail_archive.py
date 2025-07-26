"""Gmail archive action."""

from __future__ import annotations

import base64
import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib import request
from urllib.parse import urlparse
import re
import html

from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

from ..core import BaseAction
from .gdrive_upload import GDriveUploadAction


class GmailArchiveAction(BaseAction):
    """Download a Gmail message and attachments and store them."""

    def _collect_text(
        self,
        part: Dict[str, Any],
        *,
        service: Optional[Any] = None,
        msg_id: Optional[str] = None,
    ) -> List[str]:
        """Recursively collect text parts from a Gmail message payload."""

        text_parts: List[str] = []
        mime = part.get("mimeType", "")
        body = part.get("body", {})
        data = body.get("data")

        if (not data) and body.get("attachmentId") and service and msg_id:
            try:
                raw = (
                    service.users()
                    .messages()
                    .attachments()
                    .get(userId="me", messageId=msg_id, id=body["attachmentId"])
                    .execute()
                )
                data = raw.get("data")
            except Exception:
                data = None

        if data and mime in ("text/plain", "text/html"):
            try:
                text = base64.urlsafe_b64decode(data).decode("utf-8", errors="ignore")
                text_parts.append(text)
            except Exception:
                pass

        for sub in part.get("parts", []):
            text_parts.extend(self._collect_text(sub, service=service, msg_id=msg_id))

        return text_parts

    @staticmethod
    def _strip_replies(text: str) -> str:
        """Remove quoted replies from an email body."""

        lines = []
        for line in text.splitlines():
            if line.lstrip().startswith(">"):
                continue
            if re.match(r"On .* wrote:", line):
                break
            lines.append(line)
        return "\n".join(lines).strip()

    def _load_service(self, token_file: str):
        creds = Credentials.from_authorized_user_file(
            token_file,
            ["https://www.googleapis.com/auth/gmail.readonly"],
        )
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
        service = build("gmail", "v1", credentials=creds, cache_discovery=False)
        return service

    def _create_drive_folder(self, name: str, parent: Optional[str], token: str) -> str:
        metadata = {"name": name, "mimeType": "application/vnd.google-apps.folder"}
        if parent:
            metadata["parents"] = [parent]
        body = json.dumps(metadata).encode()
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }
        req = request.Request("https://www.googleapis.com/drive/v3/files", data=body, headers=headers)
        with request.urlopen(req) as resp:
            data = json.loads(resp.read().decode())
        return data["id"]

    def execute(self, data: Dict[str, Any]) -> Dict[str, Any]:
        token_file = self.params.get("token_file", "token.json")
        drive_parent = self.params.get("drive_folder_id")
        local_dir = self.params.get("local_dir")
        token = self.params.get("token") or os.environ.get("GDRIVE_TOKEN")
        save_message = bool(self.params.get("save_message", True))
        save_attachments = bool(self.params.get("save_attachments", True))
        download_links = bool(self.params.get("download_links", False))
        types = self.params.get("attachment_types")
        ext_filter = None
        if types:
            if isinstance(types, str):
                ext_filter = [t.strip().lower() for t in types.split(",") if t.strip()]
            else:
                ext_filter = [str(t).lower() for t in types]
        msg_id = data.get("id")
        if not msg_id:
            raise ValueError("Message id required")
        if not local_dir and not drive_parent:
            raise ValueError("Either local_dir or drive_folder_id must be set")

        service = self._load_service(token_file)
        msg = (
            service.users()
            .messages()
            .get(userId="me", id=msg_id, format="full")
            .execute()
        )

        headers = {h["name"].lower(): h.get("value", "") for h in msg.get("payload", {}).get("headers", [])}
        sender = headers.get("from", "")
        subject = headers.get("subject", "")
        date = headers.get("date", "")
        snippet = msg.get("snippet", "")

        attachments: List[str] = []
        files: List[tuple[str, bytes]] = []
        if save_attachments:
            for part in msg.get("payload", {}).get("parts", []):
                filename = part.get("filename")
                att_id = part.get("body", {}).get("attachmentId")
                if filename and att_id:
                    if ext_filter and not any(
                        filename.lower().endswith(ext) for ext in ext_filter
                    ):
                        continue
                    raw = (
                        service.users()
                        .messages()
                        .attachments()
                        .get(userId="me", messageId=msg_id, id=att_id)
                        .execute()
                    )
                    content = base64.urlsafe_b64decode(raw["data"])
                    files.append((filename, content))
                    attachments.append(filename)

        message_text = "\n".join(
            self._collect_text(
                msg.get("payload", {}), service=service, msg_id=msg_id
            )
        )
        message_text = self._strip_replies(message_text)
        message_text = html.unescape(message_text)

        if download_links:
            urls = set(re.findall(r"https?://[^\s\"<>]+", message_text))
            urls.update(re.findall(r'href=[\"\'](https?://[^\"\']+)', message_text))
            for url in urls:
                try:
                    with request.urlopen(url) as resp:
                        headers = getattr(resp, "headers", None)
                        if headers is not None:
                            cd = headers.get("Content-Disposition", "")
                        else:
                            cd = getattr(resp, "getheader", lambda x, default="": default)("Content-Disposition")
                        content = resp.read()
                    parsed = urlparse(url)
                    name = os.path.basename(parsed.path)
                    if not name or not Path(name).suffix:
                        m = re.search(r'filename="?([^";]+)"?', cd)
                        if m:
                            name = os.path.basename(m.group(1))
                    if not name:
                        name = "downloaded_file"
                    ext = Path(name).suffix.lower()
                    if ext_filter and ext not in ext_filter:
                        continue
                    files.append((name, content))
                    attachments.append(name)
                except Exception:
                    continue

        folder_name = str(msg_id)
        storage_path = ""
        need_storage = save_message or bool(files)
        if need_storage and local_dir:
            folder = Path(local_dir) / folder_name
            folder.mkdir(parents=True, exist_ok=True)
            if save_message:
                with open(folder / "message.txt", "w", encoding="utf-8") as fh:
                    fh.write(message_text)
            for name, content in files:
                with open(folder / name, "wb") as fh:
                    fh.write(content)
            storage_path = str(folder)
        elif need_storage:
            if not token:
                raise ValueError("token required for Google Drive upload")
            folder_id = self._create_drive_folder(folder_name, drive_parent, token)
            uploader = GDriveUploadAction({"folder_id": folder_id, "token": token})
            if save_message:
                uploader.execute({"content": message_text.encode(), "filename": "message.txt"})
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
