"""Google Sheets append action."""

from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict
from urllib import parse, request

from ..core import BaseAction


class SheetsAppendAction(BaseAction):
    """Append data to a Google Sheet."""

    def execute(self, data: Dict[str, Any]) -> None:
        """Append ``data`` to the configured Google Sheet.

        Required params are ``sheet_id`` and ``range``. ``token`` can be
        supplied in params or via the ``GDRIVE_TOKEN`` environment variable.

        The payload should contain a ``values`` list representing a row.
        """

        sheet_id = self.params.get("sheet_id")
        range_ = self.params.get("range")
        token = self.params.get("token") or os.environ.get("GDRIVE_TOKEN")
        values = data.get("values")

        if not sheet_id or not range_ or values is None or not token:
            logging.error("Google Sheets append configuration missing")
            return

        logging.info("Appending row to sheet %s range %s", sheet_id, range_)

        url = (
            f"https://sheets.googleapis.com/v4/spreadsheets/{sheet_id}/values/"
            f"{parse.quote(range_)}:append?valueInputOption=USER_ENTERED"
        )
        body = json.dumps({"values": [values]}).encode()
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

        req = request.Request(url, data=body, headers=headers)

        try:
            request.urlopen(req)
            logging.info("Google Sheets append successful")
        except Exception as exc:  # pylint: disable=broad-except
            logging.exception("Google Sheets append failed: %s", exc)
