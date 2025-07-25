"""Gmail polling trigger implementation."""

from __future__ import annotations

import logging
from typing import Any, Dict, List

from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

from ..core import BaseTrigger


class GmailPollTrigger(BaseTrigger):
    """Poll Gmail using the Gmail API."""

    def poll(self) -> List[Dict[str, Any]]:
        """Return unread messages matching the configured query.

        The configuration should provide:
        - ``token_file``: path to a Gmail OAuth2 token JSON file.
        - ``query``: Gmail search query string.
        - ``max_results`` (optional): maximum number of messages to return.

        Only a very small subset of the Gmail API is used here to keep the
        implementation lightweight. Errors are logged and an empty list is
        returned if polling fails.
        """

        token_path = self.config.get("token_file", "token.json")
        query = self.config.get("query", "label:inbox")
        max_results = int(self.config.get("max_results", 100))

        logging.info("Polling Gmail using %s with query '%s'", token_path, query)
        logging.debug("Loading credentials from %s", token_path)

        try:
            creds = Credentials.from_authorized_user_file(
                token_path,
                ["https://www.googleapis.com/auth/gmail.readonly"],
            )
            if creds.expired and creds.refresh_token:
                logging.debug("Refreshing Gmail token")
                creds.refresh(Request())  # type: ignore[attr-defined]
            logging.debug("Building Gmail service")
            service = build(
                "gmail",
                "v1",
                credentials=creds,
                cache_discovery=False,
            )

            logging.debug("Querying Gmail API")
            result = (
                service.users()
                .messages()
                .list(userId="me", q=query, maxResults=max_results)
                .execute()
            )
            logging.debug("Gmail API returned %s", result)
            messages = []
            for item in result.get("messages", []):
                msg_id = item["id"]
                msg = (
                    service.users()
                    .messages()
                    .get(userId="me", id=msg_id, format="full")
                    .execute()
                )
                msg["id"] = msg_id
                messages.append(msg)

                logging.debug("Fetched Gmail message %s", msg_id)
            logging.info("Gmail polling returned %d messages", len(messages))
            return messages
        except Exception as exc:  # pylint: disable=broad-except
            logging.exception("Gmail polling failed: %s", exc)
            return []
