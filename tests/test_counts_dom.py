"""Count-widget helpers. Selectors are the ones Anki 25.09+ actually emits."""

from __future__ import annotations

from hide_counts_until_answer.counts_dom import (
    ANSWER_BUTTON_SELECTOR,
    ANSWER_OVERLAY_STYLE,
    COUNT_CLASSES,
    LEGACY_COUNT_IDS,
    QUESTION_HOST_SELECTOR,
    bottom_bar_script,
    card_overlay_script,
    count_class_selector,
    review_side_for_show_kind,
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
    assert script.count(".remove()") == 1
    assert "hcu-count-reveal" not in script
    assert "hcu-count-park" in script
    assert "td.stat button" not in script
    assert "middle.innerHTML" not in script
    assert "outer.innerHTML" not in script
    assert "pycmd" not in script
    assert "ease1" not in script
    assert ANSWER_BUTTON_SELECTOR not in script.replace(ANSWER_BUTTON_SELECTOR, "", 1)
    for mode in ("show", "stock"):
        assert f'window.__hcuSetMode("{mode}")' in bottom_bar_script(mode)
    assert 'window.__hcuSetMode("stock")' in bottom_bar_script("nope")


def test_answer_overlay_is_centered_above_the_toolbar() -> None:
    script = bottom_bar_script("show")
    assert "td.stat button" not in script
    assert "injectedCountHost" not in script
    assert "hcu-count-reveal" not in script
    assert "20px" not in script
    assert "adjustHeightToFit" not in script
    assert "getBoundingClientRect" not in script
    assert "scrollHeight" not in script
    overlay = card_overlay_script(
        '<span class=new-count>12</span> + <span class=learn-count><u>3</u></span>'
    )
    assert "position:fixed" in overlay
    assert "left:50%" in overlay
    assert "translateX(-50%)" in overlay
    assert "bottom:8px" in overlay
    assert ANSWER_OVERLAY_STYLE in overlay
    assert "td.stat" not in overlay
    assert "adjustHeightToFit" not in overlay
    assert card_overlay_script(None).count(".remove()") == 1
    mode_only = bottom_bar_script("stock", apply=False)
    assert 'window.__hcuSetModeOnly("stock")' in mode_only
    assert 'window.__hcuSetMode("stock")' not in mode_only
    assert review_side_for_show_kind("reviewQuestion") == "question"
    assert review_side_for_show_kind("reviewAnswer") == "answer"
    assert review_side_for_show_kind("previewQuestion") is None
    assert review_side_for_show_kind("clayoutAnswer") is None
