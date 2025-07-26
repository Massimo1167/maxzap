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

    def _poll_account(
        self, token_path: str, query: str, max_results: int
    ) -> List[Dict[str, Any]]:
        """Poll a single Gmail account and return messages."""

        logging.info("Polling Gmail using %s with query '%s'", token_path, query)
        logging.debug("Loading credentials from %s", token_path)

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
        messages: List[Dict[str, Any]] = []
        for item in result.get("messages", []):
            msg_id = item["id"]
            msg = (
                service.users()
                .messages()
                .get(userId="me", id=msg_id, format="full")
                .execute()
            )
            msg["id"] = msg_id
            msg["token_file"] = token_path
            messages.append(msg)

            headers = msg.get("payload", {}).get("headers", [])
            sender = ""
            subject = ""
            for header in headers:
                name = header.get("name", "").lower()
                if name == "from":
                    sender = header.get("value", "")
                elif name == "subject":
                    subject = header.get("value", "")
                if sender and subject:
                    break
            logging.debug(
                "Fetched Gmail message %s from %s with subject %s",
                msg_id,
                sender,
                subject,
            )
        return messages

    def poll(self) -> List[Dict[str, Any]]:
        """Return unread messages matching the configured query.

        Configuration options:
        - ``token_file``: path to a Gmail OAuth2 token JSON file.
        - ``query``: Gmail search query string.
        - ``max_results`` (optional): maximum number of messages to return.
        - ``accounts`` (optional): list of account-specific dictionaries with the
          same keys as above to poll multiple mailboxes.

        Only a very small subset of the Gmail API is used here to keep the
        implementation lightweight. Errors are logged and an empty list is
        returned if polling fails.
        """
        try:
            account_cfgs = self.config.get("accounts")
            if account_cfgs:
                results: List[Dict[str, Any]] = []
                for acc in account_cfgs:
                    token_path = acc.get(
                        "token_file", self.config.get("token_file", "token.json")
                    )
                    query = acc.get("query", self.config.get("query", "label:inbox"))
                    max_results = int(
                        acc.get("max_results", self.config.get("max_results", 100))
                    )
                    results.extend(self._poll_account(token_path, query, max_results))
                logging.info("Gmail polling returned %d messages", len(results))
                return results

            token_path = self.config.get("token_file", "token.json")
            query = self.config.get("query", "label:inbox")
            max_results = int(self.config.get("max_results", 100))
            results = self._poll_account(token_path, query, max_results)
            logging.info("Gmail polling returned %d messages", len(results))
            return results
        except Exception as exc:  # pylint: disable=broad-except
            logging.exception("Gmail polling failed: %s", exc)
            return []
