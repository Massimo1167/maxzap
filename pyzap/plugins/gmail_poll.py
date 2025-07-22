"""Gmail polling trigger."""

from typing import Any, Dict, List

from ..core import BaseTrigger


class GmailPollTrigger(BaseTrigger):
    """Poll Gmail using the Gmail API."""

    def poll(self) -> List[Dict[str, Any]]:
        # TODO: Implement Gmail API polling with OAuth2
        # Return list of message payloads with unique 'id'
        return []
