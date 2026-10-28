"""Reviewer count visibility. Display only: no scheduling and no bottom-bar rewrite.

Verified against Anki 25.09 and 26.09.3 ``qt/aqt/reviewer.py``:

* ``Reviewer._remaining`` renders the counts as
  ``span.new-count``, ``span.learn-count``, and ``span.review-count``
  (the current queue count is wrapped in ``<u>``).
* ``Reviewer._showAnswerButton`` places that markup in
  ``#ansbut > span.stattxt``.
* ``Reviewer._showEaseButtons`` replaces ``#middle`` via ``showAnswer``,
  which drops those nodes. The answer buttons are ``button[data-ease]``.
* Colors come from ``ts/lib/sass/card-counts.scss``
  (``.new-count`` / ``.learn-count`` / ``.review-count``), included by
  ``qt/aqt/data/web/css/reviewer-bottom.scss``.

``#new``, ``#lrn``, and ``#rev`` are not emitted by those versions. They are
still concealed when some other bottom bar leaves them in the page.

The question side conceals the live nodes (and parks the ``.stattxt`` host
outside ``#middle`` so Anki's answer HTML does not destroy them). The answer
side leaves that host parked, so the bottom bar stays at stock height and
the ease-button intervals are untouched. The same markup is shown in the
reviewer card webview, ``position: fixed`` and centered on the viewport's
bottom edge. That edge is the top of the toolbar, so the line sits in the
gap above the bar the way the question's ``.stattxt`` floats above Show
Answer. Painting it inside the bottom document clips it (``body { overflow:
hidden }``) or lands it on the interval labels. Stock mode puts a concealed
host back into ``#ansbut`` when the watcher hid the next question early; it
does not delete a question Anki just drew.
"""

from __future__ import annotations

import json

# Class names from Reviewer._remaining in Anki 25.09 and 26.09.3.
COUNT_CLASSES: tuple[str, ...] = ("new-count", "learn-count", "review-count")

# Older bottom bars used these ids. Absent from the 25.09+ reviewer.
LEGACY_COUNT_IDS: tuple[str, ...] = ("new", "lrn", "rev")

# Answer buttons in Reviewer._answerButtons: data-ease="1" .. "4".
ANSWER_BUTTON_SELECTOR = "#middle button[data-ease]"

# Question-side host in Reviewer._showAnswerButton.
QUESTION_HOST_SELECTOR = "#ansbut > span.stattxt"

MODES: tuple[str, ...] = ("hide", "show", "stock")

# Shown in the reviewer card webview, not the bottom bar. That viewport
# already ends at the toolbar, so a small ``bottom`` is the gap above the
# bar. ``left: 50%`` and ``translateX(-50%)`` match the centered Show Answer
# counts. The line is not inside the bar, so it cannot cover ``.nobold``.
ANSWER_OVERLAY_ID = "hcu-answer-counts"
ANSWER_OVERLAY_STYLE = (
    "position:fixed;left:50%;bottom:8px;transform:translateX(-50%);"
    "z-index:1000;pointer-events:none;white-space:nowrap;font-size:small;"
    "font-weight:normal;text-align:center;margin:0;padding:0;"
)
# reviewer.css does not include card-counts.scss. These variables are set
# on the card webview, same names as the bottom bar.
ANSWER_COUNT_COLORS = (
    "#hcu-answer-counts .new-count{color:var(--state-new)}"
    "#hcu-answer-counts .learn-count{color:var(--state-learn)}"
    "#hcu-answer-counts .review-count{color:var(--state-review)}"
)


def count_class_selector() -> str:
    return ", ".join(f".{name}" for name in COUNT_CLASSES)


def legacy_id_selector() -> str:
    return ", ".join(f"#{name}" for name in LEGACY_COUNT_IDS)


def visibility_for(side: str, allowlisted: bool) -> str:
    """``hide`` on the question, ``show`` on the answer, ``stock`` otherwise."""

    if not allowlisted:
        return "stock"
    if side == "question":
        return "hide"
    if side == "answer":
        return "show"
    return "stock"


def should_restore_counts(new_state: str, old_state: str) -> bool:
    """True when the reviewer is being left, so a conceal cannot stick."""

    return old_state == "review" and new_state != "review"


def card_overlay_script(html: str | None) -> str:
    """JS for the reviewer card webview. Empty html removes the line.

    The bottom-bar document cannot show this line: ``position: fixed`` there
    is clipped by the toolbar webview. The card viewport's bottom edge is
    the top of the toolbar.
    """

    payload = html if isinstance(html, str) else ""
    return (
        "(function(){\n"
        f"  var id = {json.dumps(ANSWER_OVERLAY_ID)};\n"
        "  var node = document.getElementById(id);\n"
        f"  var html = {json.dumps(payload)};\n"
        "  if (!html) {\n"
        "    if (node) node.remove();\n"
        "    return;\n"
        "  }\n"
        "  if (!node) {\n"
        "    node = document.createElement('div');\n"
        "    node.id = id;\n"
        "    node.setAttribute('data-hcu', 'answer-counts');\n"
        f"    node.style.cssText = {json.dumps(ANSWER_OVERLAY_STYLE)};\n"
        "    (document.body || document.documentElement).appendChild(node);\n"
        "  }\n"
        "  var styleId = id + '-style';\n"
        "  if (!document.getElementById(styleId)) {\n"
        "    var style = document.createElement('style');\n"
        "    style.id = styleId;\n"
        f"    style.textContent = {json.dumps(ANSWER_COUNT_COLORS)};\n"
        "    (document.head || document.documentElement).appendChild(style);\n"
        "  }\n"
        "  node.innerHTML = html;\n"
        "})();\n"
    )


def review_side_for_show_kind(kind: str) -> str | None:
    """Map ``card_will_show`` kind to a reviewer side.

    Preview and card-layout kinds are not the reviewer bottom bar.
    """

    if kind == "reviewQuestion":
        return "question"
    if kind == "reviewAnswer":
        return "answer"
    return None


# Installed once per bottom-bar document. ``__hcuSetMode`` applies it.
# ``__hcuSetModeOnly`` updates the flag the watcher reads and does not
# touch the DOM, so it can run before Anki replaces ``#middle``.
# A MutationObserver reapplies after that replacement (including the
# delayed ease-button render).
_INSTALL_JS = r"""
(function () {
  if (window.__hcuInstalled) return;
  window.__hcuInstalled = true;

  var CLASS_SELECTOR = __CLASS_SELECTOR__;
  var LEGACY_IDS = __LEGACY_IDS__;
  var ANSWER_BUTTON_SELECTOR = __ANSWER_BUTTON_SELECTOR__;

  function countHost() {
    var direct = document.querySelector(__QUESTION_HOST_SELECTOR__);
    if (direct) return direct;
    var spans = document.querySelectorAll("#middle span.stattxt");
    for (var i = 0; i < spans.length; i++) {
      var span = spans[i];
      if (span.id === "time") continue;
      if (span.closest("#hcu-count-park")) continue;
      return span;
    }
    return null;
  }

  function hostHasCounts(host) {
    if (!host) return false;
    if (host.querySelector(CLASS_SELECTOR)) return true;
    for (var i = 0; i < LEGACY_IDS.length; i++) {
      if (host.querySelector("#" + LEGACY_IDS[i])) return true;
    }
    return false;
  }

  function legacyOutside() {
    var found = [];
    for (var i = 0; i < LEGACY_IDS.length; i++) {
      var node = document.getElementById(LEGACY_IDS[i]);
      if (!node) continue;
      if (node.closest("#hcu-count-park")) continue;
      var host = countHost();
      if (host && host.contains(node)) continue;
      found.push(node);
    }
    return found;
  }

  function conceal(node) {
    if (!node) return;
    node.setAttribute("data-hcu-concealed", "1");
    node.setAttribute("aria-hidden", "true");
    node.style.setProperty("visibility", "hidden", "important");
  }

  function unconceal(node) {
    if (!node) return;
    node.removeAttribute("data-hcu-concealed");
    node.removeAttribute("aria-hidden");
    node.style.removeProperty("visibility");
  }

  function ensurePark() {
    var park = document.getElementById("hcu-count-park");
    if (park) return park;
    park = document.createElement("div");
    park.id = "hcu-count-park";
    park.hidden = true;
    park.setAttribute("aria-hidden", "true");
    park.style.display = "none";
    document.body.appendChild(park);
    return park;
  }

  function removePark() {
    var park = document.getElementById("hcu-count-park");
    if (park) park.remove();
  }

  function remember(host) {
    if (host && host.innerHTML) {
      document.documentElement.setAttribute("data-hcu-html", host.innerHTML);
    }
  }

  function parkHost(host) {
    remember(host);
    var park = ensurePark();
    if (host.parentNode === park) return;
    park.textContent = "";
    conceal(host);
    park.appendChild(host);
  }

  function parkedHost() {
    var park = document.getElementById("hcu-count-park");
    var host = park && park.querySelector("span.stattxt");
    if (host) return host;
    var html = document.documentElement.getAttribute("data-hcu-html") || "";
    if (!html) return null;
    host = document.createElement("span");
    host.className = "stattxt";
    host.innerHTML = html;
    return host;
  }

  function forgetCounts() {
    document.documentElement.removeAttribute("data-hcu-html");
    removePark();
  }

  function hideCounts() {
    var host = countHost();
    if (host && hostHasCounts(host)) parkHost(host);
    else if (host) forgetCounts();
    var legacy = legacyOutside();
    for (var i = 0; i < legacy.length; i++) conceal(legacy[i]);
  }

  function answerIsShown() {
    return !!document.querySelector(ANSWER_BUTTON_SELECTOR);
  }

  function releaseHost(host) {
    unconceal(host);
    host.style.removeProperty("position");
    host.style.removeProperty("transform");
    host.style.removeProperty("top");
    host.style.removeProperty("left");
    host.style.removeProperty("display");
    host.style.removeProperty("text-align");
    host.style.removeProperty("white-space");
    host.style.removeProperty("font-size");
    host.style.removeProperty("font-weight");
    host.style.removeProperty("visibility");
  }

  function directCountHost(button) {
    if (!button) return null;
    var kids = button.children;
    for (var i = 0; i < kids.length; i++) {
      var child = kids[i];
      if (child.tagName === "SPAN" && child.classList.contains("stattxt")) return child;
    }
    return null;
  }

  function hostIsConcealed(host) {
    if (!host) return false;
    if (host.getAttribute("data-hcu-concealed") === "1") return true;
    if (host.closest("#hcu-count-park")) return true;
    return host.style.getPropertyValue("visibility") === "hidden";
  }

  // Anki just painted this question and the watcher has not taken its counts.
  function freshQuestionHost() {
    var live = directCountHost(document.getElementById("ansbut"));
    if (!live || hostIsConcealed(live)) return null;
    return live;
  }

  function showCounts() {
    // The parked host stays out of the bar. The card webview draws the line
    // centered in the gap above the toolbar.
    var legacy = legacyOutside();
    if (legacy.length && answerIsShown()) {
      for (var i = 0; i < legacy.length; i++) unconceal(legacy[i]);
    }
  }

  function unconcealMarked() {
    var nodes = document.querySelectorAll("[data-hcu-concealed]");
    for (var i = 0; i < nodes.length; i++) unconceal(nodes[i]);
  }

  function restoreCounts() {
    var button = document.getElementById("ansbut");
    if (freshQuestionHost()) {
      // This question's counts are already on Show Answer. Drop a parked
      // host from the previous card instead of pasting it over them.
      removePark();
      unconcealMarked();
      document.documentElement.removeAttribute("data-hcu-html");
      return;
    }
    var host = parkedHost();
    if (host && button) {
      releaseHost(host);
      if (host.parentNode !== button) button.appendChild(host);
    }
    unconcealMarked();
    removePark();
    document.documentElement.removeAttribute("data-hcu-html");
  }

  window.__hcuApply = function () {
    var mode = window.__hcuMode || "stock";
    if (mode === "hide") hideCounts();
    else if (mode === "show") showCounts();
    else restoreCounts();
  };

  window.__hcuEnsureObserver = function () {
    var middle = document.getElementById("middle");
    if (!middle || middle.__hcuObserved) return;
    var observer = new MutationObserver(function () {
      window.__hcuApply();
    });
    observer.observe(middle, { childList: true, subtree: true });
    middle.__hcuObserved = true;
  };

  function normalizeMode(mode) {
    return mode === "hide" || mode === "show" ? mode : "stock";
  }

  window.__hcuSetModeOnly = function (mode) {
    window.__hcuMode = normalizeMode(mode);
    window.__hcuEnsureObserver();
  };

  window.__hcuSetMode = function (mode) {
    window.__hcuSetModeOnly(mode);
    window.__hcuApply();
  };
})();
"""


def bottom_bar_script(mode: str, *, apply: bool = True) -> str:
    """JS that installs the conceal/show helpers and sets ``mode``.

    ``apply=False`` only updates the flag the watcher reads. ``card_will_show``
    uses that so the flag is already correct when Anki replaces ``#middle``.
    """

    if mode not in MODES:
        mode = "stock"
    script = (
        _INSTALL_JS.replace("__CLASS_SELECTOR__", json.dumps(count_class_selector()))
        .replace("__LEGACY_IDS__", json.dumps(list(LEGACY_COUNT_IDS)))
        .replace("__ANSWER_BUTTON_SELECTOR__", json.dumps(ANSWER_BUTTON_SELECTOR))
        .replace("__QUESTION_HOST_SELECTOR__", json.dumps(QUESTION_HOST_SELECTOR))
    )
    setter = "__hcuSetMode" if apply else "__hcuSetModeOnly"
    return script + f"\nif (window.{setter}) window.{setter}({json.dumps(mode)});\n"
