"""Bottom-bar behavior against the Anki 25.09.2 reviewer markup.

Anki redraws ``#middle`` (``showQuestion`` sets ``innerHTML``) before
``reviewer_did_show_question``. If the previous card was whitelisted, the
watcher is still in hide mode and will park the new question's counts.
Stock mode must put those counts back on ``#ansbut``.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

from hide_counts_until_answer.counts_dom import bottom_bar_script

# qt/aqt/reviewer.py at the 25.09.2 tag: _bottomHTML, _showAnswerButton, _remaining.
BOTTOM_SHELL = """
<center id=outer>
<table id=innertable width=100% cellspacing=0 cellpadding=0>
<tr>
<td align=start valign=top class=stat>
<button title="Edit (E)" onclick="pycmd('edit');">Edit</button></td>
<td align=center valign=top id=middle>
</td>
<td align=end valign=top class=stat>
<button title="More (M)" onclick="pycmd('more');">
More ▾
<span id=time class=stattxt></span>
</button>
</td>
</tr>
</table>
</center>
<script>
time = 0;
timerStopped = false;
</script>
"""

ANSWER_MIDDLE = """
<center><table cellpadding=0 cellspacing=0><tr>
<td align=center><button title="1" data-ease="1" onclick='pycmd("ease1");'>Again<span class="nobold">&lt;1m</span></button></td>
<td align=center><button id="defease" title="2" data-ease="2" onclick='pycmd("ease2");'>Hard<span class="nobold">&lt;6m</span></button></td>
<td align=center><button title="3" data-ease="3" onclick='pycmd("ease3");'>Good<span class="nobold">&lt;10m</span></button></td>
<td align=center><button title="4" data-ease="4" onclick='pycmd("ease4");'>Easy<span class="nobold">4d</span></button></td>
</tr></table>
"""


def _question_middle(new: int, learn: int, review: int, underline: int) -> str:
    """Same shape as Reviewer._remaining wrapped by _showAnswerButton."""

    counts = [str(new), str(learn), str(review)]
    counts[underline] = f"<u>{counts[underline]}</u>"
    remaining = (
        f"\n<span class=new-count>{counts[0]}</span> +\n"
        f"<span class=learn-count>{counts[1]}</span> +\n"
        f"<span class=review-count>{counts[2]}</span>\n"
    )
    button = (
        "<button title=\"Space\" id=\"ansbut\" onclick='pycmd(\"ans\");'>"
        f"Show Answer<span class=stattxt>{remaining}</span></button>"
    )
    return (
        "<table cellpadding=0><tr><td class=stat2 align=center>"
        f"{button}</td></tr></table>"
    )


_NODE_RUNNER = r"""
import { createRequire } from "module";
import { readFileSync } from "fs";

const require = createRequire(process.env.JSDOM_FROM);
const { JSDOM } = require("jsdom");

const shell = readFileSync(process.argv[2], "utf8");
const questionA = readFileSync(process.argv[3], "utf8");
const questionB = readFileSync(process.argv[4], "utf8");
const answer = readFileSync(process.argv[5], "utf8");
const hide = readFileSync(process.argv[6], "utf8");
const stock = readFileSync(process.argv[7], "utf8");
const show = readFileSync(process.argv[8], "utf8");
const modeOnlyStock = readFileSync(process.argv[9], "utf8");
const modeOnlyShow = readFileSync(process.argv[10], "utf8");

function page() {
  return new JSDOM(`<!doctype html><body>${shell}</body>`, {
    pretendToBeVisual: true,
    runScripts: "dangerously",
  });
}

function run(dom, source) {
  const script = dom.window.document.createElement("script");
  script.textContent = source;
  dom.window.document.body.appendChild(script);
}

function showQuestion(dom, html) {
  // reviewer-bottom.ts showQuestion → showAnswer → #middle.innerHTML
  dom.window.document.getElementById("middle").innerHTML = html;
}

function flush() {
  return new Promise((resolve) => setTimeout(resolve, 0));
}

function countHost(doc) {
  const button = doc.getElementById("ansbut");
  if (!button) return null;
  for (const child of button.children) {
    if (child.tagName === "SPAN" && child.classList.contains("stattxt")) return child;
  }
  return null;
}

function visible(host) {
  if (!host) return false;
  if (host.closest("#hcu-count-park")) return false;
  if (host.getAttribute("data-hcu-concealed") === "1") return false;
  if (host.style.getPropertyValue("visibility") === "hidden") return false;
  return true;
}

function assertAnswerCountsVisible(doc, label) {
  const reveal = doc.getElementById("hcu-count-reveal");
  if (!reveal) throw new Error(label + ": answer did not reveal counts");
  if (reveal.style.position !== "absolute") {
    throw new Error(label + ": reveal is not absolute: " + reveal.style.cssText);
  }
  if (reveal.style.padding && reveal.style.padding !== "0px") {
    throw new Error(label + ": reveal padding grows the bar: " + reveal.style.padding);
  }
  const top = parseFloat(reveal.style.top);
  if (!(top > 0)) {
    throw new Error(label + ": counts are placed above the bar: " + reveal.style.cssText);
  }
  const host = reveal.querySelector("span.stattxt");
  if (!visible(host)) {
    throw new Error(label + ": answer counts are not visible");
  }
  const shown = host.querySelector(".learn-count u");
  if (!shown || shown.textContent !== "3") {
    throw new Error(label + ": answer lost the underline");
  }
  return host;
}

const whitelisted = page();
showQuestion(whitelisted, questionA);
run(whitelisted, hide);
await flush();
const hidden = countHost(whitelisted.window.document);
if (hidden) throw new Error("whitelisted question still has counts on Show Answer");

showQuestion(whitelisted, questionB);
await flush();
const stolen = countHost(whitelisted.window.document);
if (visible(stolen)) {
  throw new Error("precondition failed: watcher did not hide the next question");
}

run(whitelisted, stock);
await flush();
const doc = whitelisted.window.document;
const restored = countHost(doc);
if (!visible(restored)) throw new Error("stock counts are not visible: " + (restored && restored.outerHTML));
const underlined = restored.querySelector("u");
if (!underlined || underlined.textContent !== "9") {
  throw new Error("wrong queue underline: " + restored.innerHTML);
}
if (restored.querySelector(".new-count").textContent !== "4") {
  throw new Error("restored the previous card: " + restored.innerHTML);
}
if (doc.querySelector("#time").style.getPropertyValue("visibility") === "hidden") {
  throw new Error("timer was hidden");
}
const eases = [...doc.querySelectorAll("#middle button[data-ease]")];
if (eases.length !== 0) throw new Error("question gained ease buttons");

const early = page();
showQuestion(early, questionA);
run(early, hide);
await flush();
run(early, modeOnlyStock);
showQuestion(early, questionB);
await flush();
const earlyHost = countHost(early.window.document);
if (!visible(earlyHost)) throw new Error("mode-only stock still hid the next question");
if (earlyHost.querySelector(".review-count u").textContent !== "9") {
  throw new Error("mode-only stock showed the previous card: " + earlyHost.innerHTML);
}

const answered = page();
showQuestion(answered, questionA);
run(answered, hide);
await flush();
const hiddenOnFront = countHost(answered.window.document);
if (hiddenOnFront) {
  throw new Error("whitelisted question still has counts on Show Answer");
}
showQuestion(answered, answer);
await flush();
run(answered, show);
await flush();
assertAnswerCountsVisible(answered.window.document, "show after flip");
const buttons = [...answered.window.document.querySelectorAll("#middle button[data-ease]")];
if (buttons.map((button) => button.getAttribute("data-ease")).join(",") !== "1,2,3,4") {
  throw new Error("ease buttons changed");
}

// card_will_show sets the mode before Anki replaces #middle. The watcher
// must reveal on that replacement, which is showAnswer.
const flipped = page();
showQuestion(flipped, questionA);
run(flipped, hide);
await flush();
run(flipped, modeOnlyShow);
showQuestion(flipped, answer);
await flush();
assertAnswerCountsVisible(flipped.window.document, "showAnswer observer");

const plain = page();
showQuestion(plain, questionA);
const untouched = countHost(plain.window.document);
if (!visible(untouched)) throw new Error("stock question is missing counts");
if (untouched.querySelector(".learn-count u").textContent !== "3") {
  throw new Error("stock question counts changed before the add-on ran");
}
run(plain, stock);
await flush();
const stockHost = countHost(plain.window.document);
if (!visible(stockHost)) throw new Error("non-whitelist question hid counts");
if (stockHost.querySelector(".learn-count u").textContent !== "3") {
  throw new Error("non-whitelist counts changed: " + stockHost.innerHTML);
}
if (plain.window.document.getElementById("hcu-count-park")) {
  throw new Error("non-whitelist question parked counts");
}
showQuestion(plain, answer);
await flush();
run(plain, stock);
await flush();
const plainDoc = plain.window.document;
if (plainDoc.querySelector("[data-hcu-concealed]")) {
  throw new Error("non-whitelist answer concealed a node");
}
if (plainDoc.getElementById("hcu-count-reveal")) {
  throw new Error("non-whitelist answer injected counts");
}
const plainEases = [...plainDoc.querySelectorAll("#middle button[data-ease]")];
if (plainEases.map((button) => button.getAttribute("data-ease")).join(",") !== "1,2,3,4") {
  throw new Error("non-whitelist ease buttons changed");
}
console.log("bottom bar regression ok");
"""


def _jsdom_node_path() -> str:
    candidates = [
        Path("/tmp/hcu-dom/node_modules"),
        Path("/tmp/hcu-jsdom-cache/node_modules"),
    ]
    for path in candidates:
        if (path / "jsdom").is_dir():
            return str(path)
    cache = Path("/tmp/hcu-jsdom-cache")
    cache.mkdir(parents=True, exist_ok=True)
    if not (cache / "package.json").is_file():
        (cache / "package.json").write_text('{"private": true}\n', encoding="utf8")
    subprocess.run(
        ["npm", "install", "jsdom@25", "--silent"],
        cwd=cache,
        check=True,
    )
    return str(cache / "node_modules")


def test_whitelisted_question_then_other_question_keeps_counts(tmp_path: Path) -> None:
    if shutil.which("node") is None:
        pytest.fail("node is required to run the bottom-bar regression")
    node_path = _jsdom_node_path()
    files = {
        "shell.html": BOTTOM_SHELL,
        "question-a.html": _question_middle(12, 3, 40, underline=1),
        "question-b.html": _question_middle(4, 5, 9, underline=2),
        "answer.html": ANSWER_MIDDLE,
        "hide.js": bottom_bar_script("hide"),
        "stock.js": bottom_bar_script("stock"),
        "show.js": bottom_bar_script("show"),
        "mode-only-stock.js": bottom_bar_script("stock", apply=False),
        "mode-only-show.js": bottom_bar_script("show", apply=False),
        "run.mjs": _NODE_RUNNER,
    }
    for name, contents in files.items():
        (tmp_path / name).write_text(contents, encoding="utf8")
    parent = str(Path(node_path).parent / "package.json")
    if not Path(parent).is_file():
        parent = str(Path(node_path).parent / "node_modules" / "jsdom" / "package.json")
    env = dict(os.environ)
    env["JSDOM_FROM"] = parent
    subprocess.run(
        [
            "node",
            str(tmp_path / "run.mjs"),
            str(tmp_path / "shell.html"),
            str(tmp_path / "question-a.html"),
            str(tmp_path / "question-b.html"),
            str(tmp_path / "answer.html"),
            str(tmp_path / "hide.js"),
            str(tmp_path / "stock.js"),
            str(tmp_path / "show.js"),
            str(tmp_path / "mode-only-stock.js"),
            str(tmp_path / "mode-only-show.js"),
        ],
        check=True,
        cwd=tmp_path,
        env=env,
    )
