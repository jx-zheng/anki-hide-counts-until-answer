"""Hide the reviewer counts on the question until the answer is shown.

Whitelisted decks only. Display only: scheduling, ease buttons, queues, and
card data are left alone. See the repository README.
"""

from __future__ import annotations


def _bootstrap() -> None:
    try:
        from aqt import gui_hooks
    except ImportError:
        return
    from .ui import install_hooks

    install_hooks(gui_hooks)


_bootstrap()
