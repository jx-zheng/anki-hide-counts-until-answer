"""Hook registration without Qt."""

from __future__ import annotations

import json
from pathlib import Path

import hide_counts_until_answer
import hide_counts_until_answer.ui as ui

ROOT = Path(__file__).resolve().parents[1]


class _Hook:
    def __init__(self) -> None:
        self.callbacks: list = []

    def append(self, callback) -> None:
        self.callbacks.append(callback)


class _Hooks:
    def __init__(self) -> None:
        self.card_will_show = _Hook()
        self.reviewer_did_show_question = _Hook()
        self.reviewer_did_show_answer = _Hook()
        self.reviewer_will_end = _Hook()
        self.state_did_change = _Hook()
        self.profile_will_close = _Hook()
        self.main_window_did_init = _Hook()


def test_package_imports_without_aqt() -> None:
    assert hide_counts_until_answer is not None


def test_install_hooks_registers_each_entry_point() -> None:
    hooks = _Hooks()
    ui.install_hooks(hooks)
    assert hooks.card_will_show.callbacks == [ui.on_card_will_show]
    assert hooks.reviewer_did_show_question.callbacks == [ui.on_show_question]
    assert hooks.reviewer_did_show_answer.callbacks == [ui.on_show_answer]
    assert hooks.reviewer_will_end.callbacks == [ui.on_reviewer_will_end]
    assert hooks.state_did_change.callbacks == [ui.on_state_change]
    assert hooks.profile_will_close.callbacks == [ui.on_profile_will_close]
    assert hooks.main_window_did_init.callbacks == [ui.on_main_window]


def test_card_will_show_returns_card_html_unchanged() -> None:
    html = "<div id=qa>front</div>"
    ui._applied = "stock"
    assert ui.on_card_will_show(html, object(), "previewQuestion") == html
    assert ui.on_card_will_show(html, object(), "reviewQuestion") == html
    assert ui.on_card_will_show(html, object(), "reviewAnswer") == html
    assert ui._applied == "stock"


def test_tools_action_mentions_choose_decks() -> None:
    assert "Choose Decks" in ui.CHOOSE_DECKS_ACTION
    assert ui.CHOOSE_DECKS_ACTION.endswith("…")


def test_manifest_and_config_docs() -> None:
    manifest = json.loads(
        (ROOT / "hide_counts_until_answer" / "manifest.json").read_text()
    )
    assert manifest["package"] == "hide_counts_until_answer"
    assert manifest["name"] == "Hide Counts Until Answer"
    assert manifest["human_version"] == "1.0.1"
    assert manifest["min_point_version"] == 250900
    docs = (ROOT / "hide_counts_until_answer" / "config.md").read_text()
    assert "enabled_deck_ids" in docs
    assert "enabled_deck_names" in docs
    assert "odid" in docs
