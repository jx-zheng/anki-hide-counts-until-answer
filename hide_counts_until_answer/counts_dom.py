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
side moves that same host back into view above the ease buttons. Stock mode
drops only the nodes this add-on created.
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

# Ignore a collapsed measurement. Anki has a known path where offsetHeight
# is 1 during reflow; applying that would squash the bottom bar.
MIN_BOTTOM_BAR_HEIGHT = 48


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


def acceptable_bottom_height(measured: object) -> int | None:
    """Pixel height worth applying, or None to leave the bar alone.

    A measurement taken mid-reflow can be 0 or 1. Applying that would
    collapse the reviewer bottom bar, so anything under
    ``MIN_BOTTOM_BAR_HEIGHT`` is ignored.
    """

    if isinstance(measured, bool):
        return None
    if isinstance(measured, str):
        text = measured.strip()
        if not text.isdigit():
            return None
        value = int(text)
    else:
        try:
            value = int(measured)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            return None
    if value < MIN_BOTTOM_BAR_HEIGHT:
        return None
    return value


# Installed once per bottom-bar document. ``__hcuSetMode`` is called on
# every question and answer. A MutationObserver reapplies after Anki
# replaces ``#middle`` (including the delayed ease-button render).
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

  function placeInFlow(host) {
    unconceal(host);
    host.style.setProperty("position", "static", "important");
    host.style.setProperty("transform", "none", "important");
    host.style.setProperty("top", "auto", "important");
    host.style.setProperty("left", "auto", "important");
    host.style.setProperty("display", "block", "important");
    host.style.setProperty("text-align", "center", "important");
    host.style.setProperty("white-space", "nowrap", "important");
    host.style.setProperty("font-size", "small", "important");
    host.style.setProperty("font-weight", "normal", "important");
    host.style.setProperty("visibility", "visible", "important");
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
    var reveal = document.getElementById("hcu-count-reveal");
    if (!reveal) {
      reveal = document.createElement("div");
      reveal.id = "hcu-count-reveal";
      reveal.setAttribute("data-hcu", "counts");
      reveal.style.cssText = "text-align:center;padding:2px 8px 12px;pointer-events:none;-webkit-user-select:none;user-select:none;";
      middle.insertBefore(reveal, middle.firstChild);
    }
    placeInFlow(host);
    if (host.parentNode !== reveal) reveal.appendChild(host);
  }

  function restoreCounts() {
    var nodes = document.querySelectorAll("[data-hcu-concealed]");
    for (var i = 0; i < nodes.length; i++) unconceal(nodes[i]);
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

  window.__hcuSetMode = function (mode) {
    window.__hcuMode = mode === "hide" || mode === "show" ? mode : "stock";
    window.__hcuEnsureObserver();
    window.__hcuApply();
  };
})();
"""


def bottom_bar_script(mode: str) -> str:
    """JS that installs the conceal/show helpers and applies ``mode``."""

    if mode not in MODES:
        mode = "stock"
    script = (
        _INSTALL_JS.replace("__CLASS_SELECTOR__", json.dumps(count_class_selector()))
        .replace("__LEGACY_IDS__", json.dumps(list(LEGACY_COUNT_IDS)))
        .replace("__ANSWER_BUTTON_SELECTOR__", json.dumps(ANSWER_BUTTON_SELECTOR))
        .replace("__QUESTION_HOST_SELECTOR__", json.dumps(QUESTION_HOST_SELECTOR))
    )
    return script + f"\nif (window.__hcuSetMode) window.__hcuSetMode({json.dumps(mode)});\n"


def bottom_height_script() -> str:
    """Measure the bottom document after a count line is added or removed.

    Uses scroll height so a fixed webview viewport does not report the old
    widget size. Does not touch buttons or call back into Python.
    """

    return """
(function () {
  var root = document.documentElement;
  if (!root) return 0;
  if (document.body) document.body.style.setProperty("min-height", "0px");
  var scroll = root.scrollHeight || 0;
  var bodyScroll = (document.body && document.body.scrollHeight) || 0;
  var offset = root.offsetHeight || 0;
  var value = scroll;
  if (bodyScroll > value) value = bodyScroll;
  if (offset > value) value = offset;
  return value;
})()
"""
