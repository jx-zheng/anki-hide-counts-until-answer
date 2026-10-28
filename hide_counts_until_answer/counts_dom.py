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
side shows that host again, absolutely positioned against the ease-button
border the way ``.stattxt`` is (``top: -3px`` and ``translateY(-100%)``).
Anchoring those offsets to the top of ``#middle`` paints the line above the
bar; ``toolbar-bottom.scss`` sets ``body { overflow: hidden }``, so the
counts stay invisible after Show Answer. The bar does not grow. Stock mode
puts a concealed host back into ``#ansbut`` when the watcher hid the next
question early; it does not delete a question Anki just drew.
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

# Horizontal placement matches ``.stattxt`` / ``.nobold`` in
# reviewer-bottom.scss. ``top`` is set in the page, against the ease-button
# border, so the line stays inside the fixed-height bar. Absolute, so the
# answer-side counts do not add a row.
REVEAL_STYLE = (
    "position:absolute;left:50%;transform:translate(-50%,-100%);"
    "white-space:nowrap;pointer-events:none;z-index:5;font-size:small;"
    "font-weight:normal;text-align:center;margin:0;padding:0;"
)

# reviewer-bottom.scss: ``#middle td[align=center]`` padding-top is 10px and
# ``button`` margin is 9px. Used when the bottom bar has not been laid out
# yet and the button's border offset measures as 0.
BUTTON_BORDER_FALLBACK = 19

# ``.stattxt`` uses ``top: -3px`` from the button border.
STATTXT_ABOVE_BUTTON = 3


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
    if (direct && !direct.closest("#hcu-count-reveal")) return direct;
    var spans = document.querySelectorAll("#middle span.stattxt");
    for (var i = 0; i < spans.length; i++) {
      var span = spans[i];
      if (span.id === "time") continue;
      if (span.closest("#hcu-count-reveal")) continue;
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
      if (node.closest("#hcu-count-park, #hcu-count-reveal")) continue;
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

  function removeReveal() {
    var reveal = document.getElementById("hcu-count-reveal");
    if (reveal) reveal.remove();
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

  function parkedOrRevealedHost() {
    var park = document.getElementById("hcu-count-park");
    var revealed = document.getElementById("hcu-count-reveal");
    var host = (park && park.querySelector("span.stattxt")) ||
      (revealed && revealed.querySelector("span.stattxt"));
    if (host) return host;
    var html = document.documentElement.getAttribute("data-hcu-html") || "";
    if (!html) return null;
    host = document.createElement("span");
    host.className = "stattxt";
    host.innerHTML = html;
    return host;
  }

  function hideCounts() {
    removeReveal();
    var host = countHost();
    if (host && hostHasCounts(host)) parkHost(host);
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
    if (host.closest("#hcu-count-park, #hcu-count-reveal")) return true;
    return host.style.getPropertyValue("visibility") === "hidden";
  }

  // Anki just painted this question and the watcher has not taken its counts.
  function freshQuestionHost() {
    var live = directCountHost(document.getElementById("ansbut"));
    if (!live || hostIsConcealed(live)) return null;
    return live;
  }

  function placeLikeStattxt(host) {
    unconceal(host);
    host.style.setProperty("position", "static", "important");
    host.style.setProperty("transform", "none", "important");
    host.style.setProperty("top", "auto", "important");
    host.style.setProperty("left", "auto", "important");
    host.style.setProperty("display", "inline", "important");
    host.style.setProperty("visibility", "visible", "important");
    host.style.setProperty("white-space", "nowrap", "important");
    host.style.setProperty("font-size", "small", "important");
    host.style.setProperty("font-weight", "normal", "important");
  }

  function easeButtonBorderTop(anchor) {
    var button = document.querySelector(ANSWER_BUTTON_SELECTOR);
    if (!button) return __BUTTON_BORDER_FALLBACK__;
    var delta = button.getBoundingClientRect().top - anchor.getBoundingClientRect().top;
    if (delta > 1) return Math.round(delta);
    return __BUTTON_BORDER_FALLBACK__;
  }

  function showCounts() {
    var legacy = legacyOutside();
    if (legacy.length && answerIsShown()) {
      for (var i = 0; i < legacy.length; i++) unconceal(legacy[i]);
    }
    if (!answerIsShown()) return;
    var middle = document.getElementById("middle");
    if (!middle) return;
    var host = parkedOrRevealedHost();
    if (!host) return;
    if (!middle.style.position) middle.style.position = "relative";
    var reveal = document.getElementById("hcu-count-reveal");
    if (!reveal) {
      reveal = document.createElement("div");
      reveal.id = "hcu-count-reveal";
      reveal.setAttribute("data-hcu", "counts");
      reveal.style.cssText = __REVEAL_STYLE__;
      middle.appendChild(reveal);
    }
    // Bottom of the line sits a few pixels above the ease buttons, then
    // translateY(-100%) lifts the text into the padding Anki already
    // reserves there. A negative top on #middle is above the webview, and
    // body { overflow: hidden } keeps it invisible.
    reveal.style.top = (easeButtonBorderTop(middle) - __STATTXT_ABOVE_BUTTON__) + "px";
    placeLikeStattxt(host);
    if (host.parentNode !== reveal) reveal.appendChild(host);
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
      removeReveal();
      removePark();
      unconcealMarked();
      document.documentElement.removeAttribute("data-hcu-html");
      return;
    }
    var park = document.getElementById("hcu-count-park");
    var reveal = document.getElementById("hcu-count-reveal");
    var host = (park && park.querySelector("span.stattxt")) ||
      (reveal && reveal.querySelector("span.stattxt"));
    if (host && button) {
      releaseHost(host);
      if (host.parentNode !== button) button.appendChild(host);
    }
    unconcealMarked();
    removeReveal();
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
        .replace("__REVEAL_STYLE__", json.dumps(REVEAL_STYLE))
        .replace("__BUTTON_BORDER_FALLBACK__", json.dumps(BUTTON_BORDER_FALLBACK))
        .replace("__STATTXT_ABOVE_BUTTON__", json.dumps(STATTXT_ABOVE_BUTTON))
    )
    setter = "__hcuSetMode" if apply else "__hcuSetModeOnly"
    return script + f"\nif (window.{setter}) window.{setter}({json.dumps(mode)});\n"
