"""Debug script for polling an IMAP mailbox.

This utility loads IMAP credentials from environment variables so that
secret values are not stored in the source code.  A `.env` file can be
used to define the variables locally during development.

Environment variables:

* ``IMAP_EMAIL`` – username of the IMAP account.
* ``IMAP_PASSWORD`` – password of the IMAP account.
* ``IMAP_HOST`` – optional host name (defaults to ``in.postassl.it``).
* ``IMAP_PORT`` – optional port number (defaults to ``993``).
* ``IMAP_SEARCH`` – optional IMAP search query (defaults to ``UNSEEN``).
"""

import logging
import os

from dotenv import load_dotenv

from pyzap.plugins.imap_poll import ImapPollTrigger


# Load variables from `.env` if present
load_dotenv()


logging.basicConfig(level=logging.INFO)


def poll(has_attachment: bool):
    """Run a polling cycle with the given attachment filter."""

    logging.info("=== Avvio poll con has_attachment=%s ===", has_attachment)
    trigger = ImapPollTrigger(
        {
            "host": os.getenv("IMAP_HOST_PURCHASE", "in.postassl.it"),
            "port": int(os.getenv("IMAP_PORT_PURCHASE", "993")),
            "username": os.getenv("IMAP_EMAIL_PURCHASE"),
            "password": os.getenv("IMAP_PASSWORD_PURCHASE"),
            "search": os.getenv("IMAP_SEARCH_PURCHASE", "UNSEEN SINCE 1-Jun-2025"),
            "has_attachment": has_attachment,
            "mark_seen": False,
        }
    )

    messages = trigger.poll()
    logging.info(
        "has_attachment=%s -> %d messaggi: %s",
        has_attachment,
        len(messages),
        [m.get("id") for m in messages],
    )
    for msg in messages:
        logging.debug("Messaggio %s, subject='%s'", msg.get("id"), msg.get("subject"))
    return messages


if __name__ == "__main__":
    poll(True)
    poll(False)

