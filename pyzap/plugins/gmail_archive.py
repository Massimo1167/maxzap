"""Gmail archive action."""

from __future__ import annotations

import base64
import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib import request

from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

from ..core import BaseAction
from .gdrive_upload import GDriveUploadAction


class GmailArchiveAction(BaseAction):
    """Download a Gmail message and attachments and store them."""

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
        for part in msg.get("payload", {}).get("parts", []):
            filename = part.get("filename")
            att_id = part.get("body", {}).get("attachmentId")
            if filename and att_id:
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
            folder_id = self._create_drive_folder(folder_name, drive_parent, token)
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
