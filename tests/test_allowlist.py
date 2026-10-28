"""Allowlist matching without aqt or a collection file."""

from __future__ import annotations

import json
from pathlib import Path

from hide_counts_until_answer.allowlist import (
    ancestor_names_of,
    card_home_deck_id,
    card_is_allowlisted,
    checklist_label,
    collection_card_allowlisted,
    config_from_checked_decks,
    initially_checked_ids,
    is_allowlisted,
    normalize_config,
)

ROOT = Path(__file__).resolve().parents[1]
DECKS = [
    ("Default", 1),
    ("Med", 5),
    ("Med::Biochem", 7),
    ("Med::Biochem::Amino", 8),
    ("Law", 9),
]


class _Decks:
    def __init__(self, rows: list[tuple[str, int]]) -> None:
        self._by_id = {deck_id: name for name, deck_id in rows}

    def have(self, deck_id: int) -> bool:
        return int(deck_id) in self._by_id

    def name(self, deck_id: int) -> str:
        return self._by_id[int(deck_id)]

    def parents(self, deck_id: int) -> list[dict[str, object]]:
        name = self._by_id[int(deck_id)]
        found = []
        for ancestor in ancestor_names_of(name):
            for parent_id, parent_name in self._by_id.items():
                if parent_name == ancestor:
                    found.append({"id": parent_id, "name": parent_name})
        return found


class _Collection:
    def __init__(self, rows: list[tuple[str, int]]) -> None:
        self.decks = _Decks(rows)


def test_shipped_config_is_empty_and_hides_nowhere() -> None:
    raw = json.loads((ROOT / "hide_counts_until_answer" / "config.json").read_text())
    assert normalize_config(raw) == {
        "enabled_deck_ids": [],
        "enabled_deck_names": [],
    }
    assert is_allowlisted(deck_id=1, deck_name="Default", config=raw) is False
    assert (
        collection_card_allowlisted(_Collection(DECKS), 7, 0, raw) is False
    )


def test_normalize_drops_junk_and_dedupes() -> None:
    raw = {
        "enabled_deck_ids": [True, False, 0, -3, 5, "7", "7", "nope", 5, 1.5],
        "enabled_deck_names": ["  Med  ", "", "   ", "Med", 3, "Law"],
        "other": "kept-out",
    }
    assert normalize_config(raw) == {
        "enabled_deck_ids": [5, 7],
        "enabled_deck_names": ["Med", "Law"],
    }
    assert normalize_config(None)["enabled_deck_ids"] == []
    assert normalize_config(["nope"])["enabled_deck_names"] == []


def test_ancestor_names_follow_double_colon() -> None:
    assert ancestor_names_of("Med") == []
    assert ancestor_names_of("Med::Biochem") == ["Med"]
    assert ancestor_names_of("Med::Biochem::Amino") == ["Med", "Med::Biochem"]
    assert ancestor_names_of("Med::") == []
    assert checklist_label("Med::Biochem::Amino") == "        Amino"
    assert checklist_label("Default") == "Default"


def test_exact_id_and_name_match_and_strangers_do_not() -> None:
    by_id = {"enabled_deck_ids": [9], "enabled_deck_names": []}
    by_name = {"enabled_deck_ids": [], "enabled_deck_names": ["Law"]}
    assert is_allowlisted(deck_id=9, deck_name="Law", config=by_id)
    assert is_allowlisted(deck_id=9, deck_name="Law", config=by_name)
    assert not is_allowlisted(deck_id=5, deck_name="Med", config=by_id)
    assert not is_allowlisted(
        deck_id=1,
        deck_name="Parenthood",
        config={"enabled_deck_ids": [], "enabled_deck_names": ["Parent"]},
    )
    assert not is_allowlisted(
        deck_id=8,
        deck_name="Med::Biochem::Amino",
        config={"enabled_deck_ids": [], "enabled_deck_names": ["Biochem"]},
    )


def test_parent_id_and_parent_name_cover_subdecks() -> None:
    assert is_allowlisted(
        deck_id=8,
        deck_name="Med::Biochem::Amino",
        ancestor_ids=[5, 7],
        config={"enabled_deck_ids": [5], "enabled_deck_names": []},
    )
    assert is_allowlisted(
        deck_id=8,
        deck_name="Med::Biochem::Amino",
        config={"enabled_deck_ids": [], "enabled_deck_names": ["Med"]},
    )
    assert is_allowlisted(
        deck_id=8,
        deck_name="Med::Biochem::Amino",
        config={"enabled_deck_ids": [], "enabled_deck_names": ["Med::Biochem"]},
    )
    assert not is_allowlisted(
        deck_id=9,
        deck_name="Law",
        ancestor_ids=[],
        config={"enabled_deck_ids": [5], "enabled_deck_names": ["Med"]},
    )


def test_filtered_card_uses_odid_home_deck() -> None:
    assert card_home_deck_id(99, 5) == 5
    assert card_home_deck_id(99, 0) == 99
    assert card_home_deck_id(99, "0") == 99
    assert card_home_deck_id(99, "5") == 5

    home = {"enabled_deck_ids": [5], "enabled_deck_names": []}
    assert card_is_allowlisted(
        did=99,
        odid=5,
        home_deck_name="Med",
        config=home,
    )
    assert not card_is_allowlisted(
        did=99,
        odid=0,
        home_deck_name="Free Review - Med",
        config=home,
    )
    assert card_is_allowlisted(
        did=99,
        odid=8,
        home_deck_name="Med::Biochem::Amino",
        home_ancestor_ids=[5, 7],
        config={"enabled_deck_ids": [], "enabled_deck_names": ["Med::Biochem"]},
    )


def test_collection_lookup_uses_home_deck_and_parent_id() -> None:
    col = _Collection(DECKS)
    parent = {"enabled_deck_ids": [5], "enabled_deck_names": []}
    assert collection_card_allowlisted(col, 99, 8, parent)
    assert collection_card_allowlisted(col, 7, 0, parent)
    assert not collection_card_allowlisted(col, 99, 0, parent)
    assert not collection_card_allowlisted(col, 99, 42, parent)
    assert collection_card_allowlisted(
        col,
        99,
        8,
        {"enabled_deck_ids": [], "enabled_deck_names": ["Med"]},
    )


def test_checklist_checks_exact_rows_and_writes_ids_plus_names() -> None:
    config = {
        "enabled_deck_ids": [5],
        "enabled_deck_names": ["Law"],
        "note": "keep",
    }
    assert initially_checked_ids(DECKS, config) == [5, 9]
    saved = config_from_checked_decks(DECKS, [5], config)
    assert saved["enabled_deck_ids"] == [5]
    assert saved["enabled_deck_names"] == ["Med"]
    assert saved["note"] == "keep"
    assert is_allowlisted(
        deck_id=8,
        deck_name="Med::Biochem::Amino",
        ancestor_ids=[5, 7],
        config=saved,
    )
    cleared = config_from_checked_decks(DECKS, [], config)
    assert cleared["enabled_deck_ids"] == []
    assert cleared["enabled_deck_names"] == []
    assert not is_allowlisted(deck_id=5, deck_name="Med", config=cleared)
