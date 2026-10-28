"""Count-widget helpers. Selectors are the ones Anki 25.09+ actually emits."""

from __future__ import annotations

from hide_counts_until_answer.counts_dom import (
    ANSWER_BUTTON_SELECTOR,
    COUNT_CLASSES,
    LEGACY_COUNT_IDS,
    MIN_BOTTOM_BAR_HEIGHT,
    QUESTION_HOST_SELECTOR,
    acceptable_bottom_height,
    bottom_bar_script,
    bottom_height_script,
    count_class_selector,
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
    assert "ease" not in script.replace(ANSWER_BUTTON_SELECTOR, "")
    for mode in ("show", "stock"):
        assert f'window.__hcuSetMode("{mode}")' in bottom_bar_script(mode)
    assert 'window.__hcuSetMode("stock")' in bottom_bar_script("nope")


def test_height_script_reads_content_and_rejects_collapsed_measurements() -> None:
    script = bottom_height_script()
    assert "scrollHeight" in script
    assert "pycmd" not in script
    assert acceptable_bottom_height(None) is None
    assert acceptable_bottom_height(True) is None
    assert acceptable_bottom_height(1) is None
    assert acceptable_bottom_height(MIN_BOTTOM_BAR_HEIGHT - 1) is None
    assert acceptable_bottom_height(MIN_BOTTOM_BAR_HEIGHT) == MIN_BOTTOM_BAR_HEIGHT
    assert acceptable_bottom_height(80.2) == 80
    assert acceptable_bottom_height("72") == 72
    assert acceptable_bottom_height("1") is None
    assert acceptable_bottom_height("tall") is None
