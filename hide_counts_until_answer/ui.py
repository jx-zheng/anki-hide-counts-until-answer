"""Tools-menu checklist and reviewer hooks.

Qt and ``aqt`` are imported inside functions so unit tests can import this
module without Anki.
"""

from __future__ import annotations

import logging
from typing import Any

from .allowlist import (
    checklist_label,
    collection_card_allowlisted,
    config_from_checked_decks,
    initially_checked_ids,
    normalize_config,
)
from .counts_dom import (
    bottom_bar_script,
    card_overlay_script,
    review_side_for_show_kind,
    should_restore_counts,
    visibility_for,
)

logger = logging.getLogger(__name__)

CHOOSE_DECKS_ACTION = "Hide Counts Until Answer: Choose Decks…"
DIALOG_TITLE = "Hide Counts Until Answer"
HELP_TEXT = (
    "Checked decks hide the new, learning, and review counts on the question. "
    "The counts come back after the answer is shown. A checked parent also "
    "covers its subdecks. Nothing is hidden until at least one deck is checked. "
    "Filtered decks such as Free Review follow the card's home deck."
)

# Last mode actually applied to the bottom bar. "stock" means this session
# has not concealed anything, so other decks are not touched.
_applied = "stock"
_menu_ready = False


def install_hooks(gui_hooks: Any) -> None:
    # Before Anki replaces #middle. Filter hook: return the card HTML unchanged.
    gui_hooks.card_will_show.append(on_card_will_show)
    gui_hooks.reviewer_did_show_question.append(on_show_question)
    gui_hooks.reviewer_did_show_answer.append(on_show_answer)
    gui_hooks.reviewer_will_end.append(on_reviewer_will_end)
    gui_hooks.state_did_change.append(on_state_change)
    gui_hooks.profile_will_close.append(on_profile_will_close)
    gui_hooks.main_window_did_init.append(on_main_window)
    try:
        from aqt import mw

        if getattr(mw, "form", None) is not None:
            on_main_window()
    except Exception:
        logger.debug("main window is not ready for the deck checklist", exc_info=True)


def on_card_will_show(text: str, card: Any, kind: str) -> str:
    """Set the watcher mode before the bottom bar redraws. Card HTML is unchanged."""

    side = review_side_for_show_kind(kind)
    if side is None:
        return text
    try:
        allowlisted = _card_allowlisted(card)
    except Exception:
        logger.debug("allowlist lookup failed", exc_info=True)
        allowlisted = False
    try:
        _queue_mode_only(visibility_for(side, allowlisted))
    except Exception:
        logger.debug("count mode update failed", exc_info=True)
    return text


def on_show_question(card: Any, *_args: Any) -> None:
    _clear_answer_overlay()
    _on_review_side(card, "question")
    if _applied == "hide":
        _schedule_retry(card, "question", "hide")


def on_show_answer(card: Any, *_args: Any) -> None:
    _on_review_side(card, "answer")
    if _applied == "show":
        _schedule_retry(card, "answer", "show")
        _publish_answer_counts(getattr(card, "id", None))


def on_reviewer_will_end(*_args: Any) -> None:
    _clear_answer_overlay()
    _apply_mode("stock")


def on_state_change(new_state: str, old_state: str, *_args: Any) -> None:
    if should_restore_counts(new_state, old_state):
        _clear_answer_overlay()
        _apply_mode("stock")


def on_profile_will_close(*_args: Any) -> None:
    global _applied
    _applied = "stock"


def on_main_window(*_args: Any) -> None:
    global _menu_ready
    if _menu_ready:
        return
    from aqt import mw
    from aqt.qt import QAction
    from aqt.utils import qconnect

    mw.addonManager.setConfigAction(_package(), _open_deck_checklist)
    action = QAction(CHOOSE_DECKS_ACTION, mw)
    action.setObjectName("hideCountsUntilAnswerChooseDecks")
    qconnect(action.triggered, _open_deck_checklist)
    mw.form.menuTools.addSeparator()
    mw.form.menuTools.addAction(action)
    _menu_ready = True


def _on_review_side(card: Any, side: str) -> None:
    try:
        allowlisted = _card_allowlisted(card)
    except Exception:
        logger.debug("allowlist lookup failed", exc_info=True)
        allowlisted = False
    _apply_mode(visibility_for(side, allowlisted))


def _card_allowlisted(card: Any) -> bool:
    from aqt import mw

    if card is None or mw.col is None:
        return False
    did = int(card.did)
    odid = int(getattr(card, "odid", 0) or 0)
    return collection_card_allowlisted(mw.col, did, odid, _read_config())


def _read_config() -> dict[str, Any]:
    from aqt import mw

    package = _package()
    raw = mw.addonManager.getConfig(package)
    if not isinstance(raw, dict):
        return normalize_config(None)
    return raw


def _package() -> str:
    from aqt import mw

    return mw.addonManager.addonFromModule(__name__)


def _queue_mode_only(mode: str) -> None:
    """Tell the page which mode is next, without touching the current DOM.

    ``card_will_show`` runs before ``_showAnswerButton`` / ``_showEaseButtons``
    queue their ``eval``. The watcher then sees this flag when ``#middle``
    is replaced, including a question that follows another question with no
    answer in between.
    """

    if mode == "stock" and _applied == "stock":
        return
    _eval_bottom(bottom_bar_script(mode, apply=False))


def _apply_mode(mode: str) -> None:
    global _applied
    if mode == "stock" and _applied == "stock":
        return
    _applied = mode
    _eval_bottom(bottom_bar_script(mode))


_COUNT_HTML_JS = 'document.documentElement.getAttribute("data-hcu-html") || ""'


def _publish_answer_counts(card_id: Any) -> None:
    """Copy the parked count markup into the card webview, above the toolbar."""

    web = _bottom_web()
    if web is None or not hasattr(web, "evalWithCallback"):
        return

    def on_html(html: Any) -> None:
        if _applied != "show" or not _still_on_side(card_id, "answer"):
            return
        if not isinstance(html, str) or not html.strip():
            _clear_answer_overlay()
            return
        _eval_reviewer(card_overlay_script(html))

    try:
        web.evalWithCallback(_COUNT_HTML_JS, on_html)
    except Exception:
        logger.debug("could not read parked counts", exc_info=True)


def _clear_answer_overlay() -> None:
    _eval_reviewer(card_overlay_script(None))


def _eval_reviewer(script: str) -> None:
    web = _reviewer_web()
    if web is None:
        return
    try:
        web.eval(script)
    except Exception:
        logger.debug("card overlay eval failed", exc_info=True)


def _reviewer_web() -> Any:
    from aqt import mw

    reviewer = getattr(mw, "reviewer", None)
    web = getattr(reviewer, "web", None) if reviewer is not None else None
    if web is not None:
        return web
    return getattr(mw, "web", None)


def _eval_bottom(script: str) -> None:
    web = _bottom_web()
    if web is None:
        return
    try:
        web.eval(script)
    except Exception:
        logger.debug("bottom bar eval failed", exc_info=True)


def _bottom_web() -> Any:
    from aqt import mw

    reviewer = getattr(mw, "reviewer", None)
    bottom = getattr(reviewer, "bottom", None) if reviewer is not None else None
    web = getattr(bottom, "web", None) if bottom is not None else None
    if web is not None:
        return web
    return getattr(mw, "bottomWeb", None)


def _schedule_retry(card: Any, side: str, mode: str) -> None:
    card_id = getattr(card, "id", None)
    if card_id is None:
        return

    def retry() -> None:
        if _applied != mode or not _still_on_side(card_id, side):
            return
        _eval_bottom(bottom_bar_script(mode))
        if mode == "show":
            _publish_answer_counts(card_id)

    _single_shot(80 if side == "answer" else 50, retry)


def _still_on_side(card_id: Any, side: str) -> bool:
    from aqt import mw

    reviewer = getattr(mw, "reviewer", None)
    if mw.state != "review" or reviewer is None:
        return False
    if getattr(reviewer, "state", None) != side:
        return False
    current = getattr(reviewer, "card", None)
    if current is None:
        return False
    try:
        return int(current.id) == int(card_id)
    except (TypeError, ValueError):
        return False


def _single_shot(ms: int, func: Any) -> None:
    try:
        from aqt import mw

        mw.progress.single_shot(ms, func, False)
    except Exception:
        logger.debug("could not schedule a bottom-bar update", exc_info=True)


def _open_deck_checklist() -> bool:
    """Config button and Tools action. False lets Anki open the JSON editor."""

    from aqt import mw
    from aqt.utils import showWarning, tooltip

    if mw.col is None:
        return False
    try:
        saved = _run_deck_dialog(mw)
    except Exception:
        logger.exception("deck checklist failed")
        showWarning("Hide Counts Until Answer could not open the deck list.")
        return False
    if saved:
        tooltip("Deck list saved.", parent=mw)
    return True


def _run_deck_dialog(mw: Any) -> bool:
    from aqt.qt import (
        QDialog,
        QDialogButtonBox,
        QLabel,
        QListWidget,
        QListWidgetItem,
        Qt,
        QVBoxLayout,
    )
    from aqt.utils import qconnect

    rows = _study_deck_rows(mw.col)
    previous = _read_config()
    checked = set(initially_checked_ids(rows, previous))

    dialog = QDialog(mw)
    dialog.setWindowTitle(DIALOG_TITLE)
    dialog.setWindowModality(Qt.WindowModality.WindowModal)
    layout = QVBoxLayout(dialog)
    help_label = QLabel(HELP_TEXT)
    help_label.setWordWrap(True)
    layout.addWidget(help_label)

    deck_list = QListWidget()
    for name, deck_id in rows:
        item = QListWidgetItem(checklist_label(name))
        item.setToolTip(name)
        item.setData(Qt.ItemDataRole.UserRole, deck_id)
        item.setFlags(
            Qt.ItemFlag.ItemIsEnabled
            | Qt.ItemFlag.ItemIsSelectable
            | Qt.ItemFlag.ItemIsUserCheckable
        )
        item.setCheckState(
            Qt.CheckState.Checked if deck_id in checked else Qt.CheckState.Unchecked
        )
        deck_list.addItem(item)
    layout.addWidget(deck_list)

    buttons = QDialogButtonBox(
        QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
    )
    qconnect(buttons.accepted, dialog.accept)
    qconnect(buttons.rejected, dialog.reject)
    layout.addWidget(buttons)
    dialog.resize(440, 520)

    if dialog.exec() != QDialog.DialogCode.Accepted:
        return False

    chosen: list[int] = []
    for index in range(deck_list.count()):
        item = deck_list.item(index)
        if item.checkState() != Qt.CheckState.Checked:
            continue
        chosen.append(int(item.data(Qt.ItemDataRole.UserRole)))

    updated = config_from_checked_decks(rows, chosen, previous)
    mw.addonManager.writeConfig(_package(), updated)
    return True


def _study_deck_rows(col: Any) -> list[tuple[str, int]]:
    """Normal decks only. Filtered decks are matched through the home deck."""

    rows: list[tuple[str, int]] = []
    for entry in col.decks.all_names_and_ids(
        skip_empty_default=False, include_filtered=False
    ):
        rows.append((str(entry.name), int(entry.id)))
    return rows
