"""Deck allowlist. Empty means hide counts nowhere.

A checked parent covers subdecks. Checklist code stores ids; names are an
optional exact-name match, and a parent name covers names under it via ``::``.

Filtered decks (Free Review, custom study) are matched on the home deck:
``odid`` when Anki set it, otherwise ``did``.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from typing import Any

ENABLED_DECK_IDS = "enabled_deck_ids"
ENABLED_DECK_NAMES = "enabled_deck_names"


def _as_list(value: Any) -> list[Any]:
    if isinstance(value, (list, tuple)):
        return list(value)
    return []


def _as_deck_id(value: Any) -> int | None:
    """Positive deck id. Bools and fractional numbers are rejected."""

    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value if value > 0 else None
    if isinstance(value, str):
        text = value.strip()
        if text.isdigit():
            number = int(text)
            return number if number > 0 else None
    return None


def _as_deck_name(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    name = value.strip()
    return name or None


def normalize_config(raw: Any) -> dict[str, list[Any]]:
    """Copy the allowlist keys into a stable, deduped shape.

    Unknown keys are dropped. Callers that write config and want to keep
    other keys should start from the previous dict themselves.
    """

    source = raw if isinstance(raw, dict) else {}
    ids: list[int] = []
    seen_ids: set[int] = set()
    for item in _as_list(source.get(ENABLED_DECK_IDS)):
        deck_id = _as_deck_id(item)
        if deck_id is None or deck_id in seen_ids:
            continue
        seen_ids.add(deck_id)
        ids.append(deck_id)

    names: list[str] = []
    seen_names: set[str] = set()
    for item in _as_list(source.get(ENABLED_DECK_NAMES)):
        name = _as_deck_name(item)
        if name is None or name in seen_names:
            continue
        seen_names.add(name)
        names.append(name)

    return {ENABLED_DECK_IDS: ids, ENABLED_DECK_NAMES: names}


def ancestor_names_of(deck_name: str) -> list[str]:
    """Full names of ancestor decks, outermost first.

    ``Med::Biochem::Amino`` -> ``["Med", "Med::Biochem"]``.
    A name without ``::`` has no ancestors. Empty pieces are skipped.
    """

    if not isinstance(deck_name, str) or "::" not in deck_name:
        return []
    parts = [part for part in deck_name.split("::") if part]
    names: list[str] = []
    for index in range(1, len(parts)):
        names.append("::".join(parts[:index]))
    return names


def checklist_label(deck_name: str) -> str:
    """Indented leaf name for the deck checklist."""

    if not isinstance(deck_name, str):
        return ""
    parts = [part for part in deck_name.split("::") if part]
    if not parts:
        return deck_name.strip()
    return ("    " * (len(parts) - 1)) + parts[-1]


def card_home_deck_id(did: int, odid: int) -> int:
    """Home deck for allowlist checks.

    Anki sets ``odid`` while a card sits in a filtered deck (Free Review and
    custom study included). When that is set, the home deck is what the
    allowlist sees. Otherwise the card's ``did`` is the home deck.
    """

    original = _as_deck_id(odid)
    if original is not None:
        return original
    current = _as_deck_id(did)
    if current is not None:
        return current
    return 0


def is_allowlisted(
    *,
    deck_id: int,
    deck_name: str,
    ancestor_ids: Iterable[int] = (),
    config: Any = None,
) -> bool:
    """True when this deck or an ancestor is on the allowlist.

    An empty allowlist matches nothing. ``ancestor_ids`` are the parent deck
    ids, outermost first. Ancestor names are taken from ``deck_name``.
    """

    normalized = normalize_config(config)
    enabled_ids = set(normalized[ENABLED_DECK_IDS])
    enabled_names = set(normalized[ENABLED_DECK_NAMES])
    if not enabled_ids and not enabled_names:
        return False

    own_id = _as_deck_id(deck_id)
    if own_id is not None and own_id in enabled_ids:
        return True
    if isinstance(deck_name, str) and deck_name in enabled_names:
        return True
    for raw_id in ancestor_ids:
        parent_id = _as_deck_id(raw_id)
        if parent_id is not None and parent_id in enabled_ids:
            return True
    if isinstance(deck_name, str):
        for ancestor in ancestor_names_of(deck_name):
            if ancestor in enabled_names:
                return True
    return False


def card_is_allowlisted(
    *,
    did: int,
    odid: int,
    home_deck_name: str,
    home_ancestor_ids: Iterable[int] = (),
    config: Any = None,
) -> bool:
    """Allowlist check for one card, using the home deck when ``odid`` is set."""

    return is_allowlisted(
        deck_id=card_home_deck_id(did, odid),
        deck_name=home_deck_name,
        ancestor_ids=home_ancestor_ids,
        config=config,
    )


def _parent_id(parent: Any) -> int | None:
    if isinstance(parent, dict):
        return _as_deck_id(parent.get("id"))
    return _as_deck_id(getattr(parent, "id", None))


def home_deck_context(col: Any, did: int, odid: int) -> tuple[int, str, list[int]] | None:
    """Resolve ``(home id, home name, ancestor ids)`` from a collection.

    Returns None when the home deck is gone, so the caller hides nothing.
    ``col.decks`` only needs ``have``, ``name``, and ``parents``.
    """

    home_id = card_home_deck_id(did, odid)
    if home_id <= 0:
        return None
    decks = col.decks
    if not decks.have(home_id):
        return None
    name = decks.name(home_id)
    if not isinstance(name, str) or not name:
        return None
    ancestor_ids: list[int] = []
    for parent in decks.parents(home_id):
        parent_id = _parent_id(parent)
        if parent_id is not None:
            ancestor_ids.append(parent_id)
    return home_id, name, ancestor_ids


def collection_card_allowlisted(col: Any, did: int, odid: int, config: Any) -> bool:
    """True when the card's home deck (or an ancestor) is allowlisted."""

    context = home_deck_context(col, did, odid)
    if context is None:
        return False
    home_id, name, ancestor_ids = context
    return is_allowlisted(
        deck_id=home_id,
        deck_name=name,
        ancestor_ids=ancestor_ids,
        config=config,
    )


def initially_checked_ids(
    decks: Sequence[tuple[str, int]], config: Any
) -> list[int]:
    """Ids the checklist shows as checked.

    Exact id or exact name only. A covered subdeck stays unchecked so saving
    still records the parent id, which continues to cover new children.
    """

    normalized = normalize_config(config)
    enabled_ids = set(normalized[ENABLED_DECK_IDS])
    enabled_names = set(normalized[ENABLED_DECK_NAMES])
    checked: list[int] = []
    for name, deck_id in decks:
        parsed = _as_deck_id(deck_id)
        if parsed is None:
            continue
        if parsed in enabled_ids or name in enabled_names:
            checked.append(parsed)
    return checked


def config_from_checked_decks(
    decks: Sequence[tuple[str, int]],
    checked_ids: Iterable[int],
    previous: Any = None,
) -> dict[str, Any]:
    """Allowlist written by the checklist.

    Ids and the current names of the checked rows are stored. Order follows
    ``decks``. Other keys already in ``previous`` are kept.
    """

    checked: set[int] = set()
    for item in checked_ids:
        parsed = _as_deck_id(item)
        if parsed is not None:
            checked.add(parsed)

    ids: list[int] = []
    names: list[str] = []
    for name, deck_id in decks:
        parsed = _as_deck_id(deck_id)
        deck_name = _as_deck_name(name)
        if parsed is None or deck_name is None or parsed not in checked:
            continue
        ids.append(parsed)
        names.append(deck_name)

    base: dict[str, Any]
    if isinstance(previous, dict):
        base = dict(previous)
    else:
        base = {}
    base[ENABLED_DECK_IDS] = ids
    base[ENABLED_DECK_NAMES] = names
    return base
