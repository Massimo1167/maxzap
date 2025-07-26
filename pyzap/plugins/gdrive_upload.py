"""Google Drive upload action."""

from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict
from urllib import request

from ..core import BaseAction


class GDriveUploadAction(BaseAction):
    """Upload a file to Google Drive."""

    def execute(self, data: Dict[str, Any]) -> None:
        """Upload ``data`` to Google Drive using the REST API.

        Expected params:
            - ``folder_id``: destination Drive folder
            - ``token`` (optional): OAuth bearer token. If omitted the
              ``GDRIVE_TOKEN`` environment variable is used.

        The payload should provide either ``file_path`` or ``content`` and an
        optional ``filename``.
        """

        folder_id = self.params.get("folder_id")
        token = self.params.get("token") or os.environ.get("GDRIVE_TOKEN")
        file_path = data.get("file_path")
        filename = data.get("filename")
        content = data.get("content")

        if file_path:
            try:
                filename = filename or os.path.basename(file_path)
                with open(file_path, "rb") as fh:
                    content = fh.read()
            except FileNotFoundError:
                logging.error("File %s not found", file_path)
                return

        missing = []
        if not folder_id:
            missing.append("folder_id")
        if not token:
            missing.append("token")
        if content is None:
            missing.append("content")

        if missing:
            logging.error(
                "Google Drive upload configuration missing: %s",
                ", ".join(missing),
            )
            return

        filename = filename or "upload.txt"
        logging.info("Uploading %s to Google Drive folder %s", filename, folder_id)

        metadata = {"name": filename, "parents": [folder_id]}
        boundary = "pyzap_boundary"
        body = (
            f"--{boundary}\r\n"
            "Content-Type: application/json; charset=UTF-8\r\n\r\n"
            f"{json.dumps(metadata)}\r\n"
            f"--{boundary}\r\n"
            "Content-Type: application/octet-stream\r\n\r\n"
        ).encode() + content + f"\r\n--{boundary}--\r\n".encode()

        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": f"multipart/related; boundary={boundary}",
        }
        req = request.Request(
            "https://www.googleapis.com/upload/drive/v3/files?uploadType=multipart",
            data=body,
            headers=headers,
        )

        try:
            request.urlopen(req)
            logging.info("Google Drive upload successful")
        except Exception as exc:  # pylint: disable=broad-except
            logging.exception("Google Drive upload failed: %s", exc)
