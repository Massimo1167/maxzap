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
        if values is None:
            fields = self.params.get("fields")
            if fields:
                values = [data.get(f) for f in fields]

        missing = []
        if not sheet_id:
            missing.append("sheet_id")
        if not range_:
            missing.append("range")
        if values is None:
            missing.append("values")
        if not token:
            missing.append("token")

        if missing:
            raise ValueError(
                "Google Sheets append configuration missing: %s" % ", ".join(missing)
            )

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
            raise RuntimeError("Google Sheets append failed") from exc
