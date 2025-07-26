"""Slack notification action."""

from __future__ import annotations

import json
import logging
from typing import Any, Dict
from urllib import request

from ..core import BaseAction


class SlackNotifyAction(BaseAction):
    """Send a notification to Slack via webhook."""

    def execute(self, data: Dict[str, Any]) -> None:
        """Send a message to the configured Slack webhook."""

        webhook = self.params.get("webhook_url")
        text = data.get("text") or data.get("message")

        missing = []
        if not webhook:
            missing.append("webhook_url")
        if text is None:
            missing.append("text")

        if missing:
            logging.error(
                "Slack webhook configuration missing: %s",
                ", ".join(missing),
            )
            return

        logging.info("Sending Slack notification")

        body = json.dumps({"text": text}).encode()
        req = request.Request(webhook, data=body, headers={"Content-Type": "application/json"})

        try:
            request.urlopen(req)
            logging.info("Slack notification sent")
        except Exception as exc:  # pylint: disable=broad-except
            logging.exception("Slack notification failed: %s", exc)
