"""Count-widget helpers. Selectors are the ones Anki 25.09+ actually emits."""

from __future__ import annotations

from hide_counts_until_answer.counts_dom import (
    ANSWER_BUTTON_SELECTOR,
    ANSWER_ROW_HEIGHT,
    COUNT_CLASSES,
    LEGACY_COUNT_IDS,
    QUESTION_HOST_SELECTOR,
    bottom_bar_script,
    count_class_selector,
    review_side_for_show_kind,
    refit_action,
    row_is_present,
    should_refit_bottom,
    should_restore_counts,
    visibility_for,
)


def test_visibility_is_question_hide_and_answer_show() -> None:
    assert visibility_for("question", True) == "hide"
    assert visibility_for("answer", True) == "show"
    assert visibility_for("question", False) == "stock"
    assert visibility_for("answer", False) == "stock"
    assert visibility_for("transition", True) == "stock"


def test_restore_only_when_leaving_review() -> None:
    assert should_restore_counts("overview", "review")
    assert should_restore_counts("deckBrowser", "review")
    assert not should_restore_counts("review", "review")
    assert not should_restore_counts("review", "overview")
    assert not should_restore_counts("overview", "deckBrowser")


def test_script_uses_verified_selectors_and_does_not_drive_scheduling() -> None:
    script = bottom_bar_script("hide")
    assert count_class_selector() == ".new-count, .learn-count, .review-count"
    for name in COUNT_CLASSES:
        assert f".{name}" in script
    for legacy in LEGACY_COUNT_IDS:
        assert f'"{legacy}"' in script
    assert QUESTION_HOST_SELECTOR in script
    assert ANSWER_BUTTON_SELECTOR in script
    assert 'window.__hcuSetMode("hide")' in script
    assert "visibility" in script
    assert "data-hcu-concealed" in script
    assert "data-hcu-html" in script
    assert script.count(".remove()") == 2
    assert "hcu-count-reveal" in script
    assert "hcu-count-park" in script
    assert "middle.innerHTML" not in script
    assert "outer.innerHTML" not in script
    assert "pycmd" not in script
    assert "ease1" not in script
    assert ANSWER_BUTTON_SELECTOR not in script.replace(ANSWER_BUTTON_SELECTOR, "", 1)
    for mode in ("show", "stock"):
        assert f'window.__hcuSetMode("{mode}")' in bottom_bar_script(mode)
    assert 'window.__hcuSetMode("stock")' in bottom_bar_script("nope")


def test_answer_counts_use_stock_stattxt_above_the_buttons() -> None:
    script = bottom_bar_script("show")
    assert f'row.style.height = "{ANSWER_ROW_HEIGHT}"' in script
    assert "data-hcu-line" in script
    assert "position:absolute;left:0;right:0;bottom:0" in script
    assert "left:50%" not in script
    assert "left: 50%" not in script
    assert "getBoundingClientRect" not in script
    assert "scrollHeight" not in script
    assert "padding:2px 8px 12px" not in script
    assert should_refit_bottom("show", "hide")
    assert should_refit_bottom("hide", "show")
    assert should_refit_bottom("stock", "show")
    assert not should_refit_bottom("hide", "hide")
    assert not should_refit_bottom("stock", "stock")
    assert refit_action("show", True, hidden=True) == "skip"
    assert refit_action("hide", False, hidden=True) == "skip"
    assert refit_action("show", False, hidden=False) == "wait"
    assert refit_action("show", True, hidden=False) == "refit"
    assert refit_action("hide", False, hidden=False) == "refit"
    assert refit_action("stock", False, hidden=False) == "refit"
    assert row_is_present(True) is True
    assert row_is_present(1) is True
    assert row_is_present("true") is True
    assert row_is_present(False) is False
    assert row_is_present("false") is False
    assert row_is_present(None) is False
    mode_only = bottom_bar_script("stock", apply=False)
    assert 'window.__hcuSetModeOnly("stock")' in mode_only
    assert 'window.__hcuSetMode("stock")' not in mode_only
    assert review_side_for_show_kind("reviewQuestion") == "question"
    assert review_side_for_show_kind("reviewAnswer") == "answer"
    assert review_side_for_show_kind("previewQuestion") is None
    assert review_side_for_show_kind("clayoutAnswer") is None
