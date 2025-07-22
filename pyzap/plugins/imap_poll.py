"""IMAP polling trigger."""

from typing import Any, Dict, List

from ..core import BaseTrigger


class ImapPollTrigger(BaseTrigger):
    """Poll an IMAP server for new messages."""

    def poll(self) -> List[Dict[str, Any]]:
        # TODO: Implement IMAP polling
        return []
