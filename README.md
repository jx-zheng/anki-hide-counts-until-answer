# Hide Counts Until Answer

Anki add-on: on whitelisted decks, hide the bottom-bar new / learning / review counts on the **question**, and show them again after the **answer**. Every other deck keeps stock Anki behavior.

This is display only. It does not answer cards, edit ease buttons, change queues, or write the collection. The only thing it saves is its own add-on config.

## What you see

Anki 25.09 and 26.09.3 draw those counts in `Reviewer._remaining` (`qt/aqt/reviewer.py`) as:

```html
<span class=new-count>…</span> +
<span class=learn-count>…</span> +
<span class=review-count>…</span>
```

That block sits in `#ansbut > span.stattxt`, above **Show Answer**. The current queue's number is underlined. Colors come from `.new-count`, `.learn-count`, and `.review-count` in Anki's reviewer bottom stylesheet.

Showing the answer replaces `#middle` with the ease buttons (`button[data-ease]`), so those nodes would otherwise disappear. On a whitelisted deck this add-on:

1. Conceals the live count nodes on the question (`visibility: hidden`) and parks that `.stattxt` host outside `#middle`, so the answer render does not destroy it.
2. After the answer is shown, mounts that same `.stattxt` host on an in-flow row above the ease buttons and leaves Anki's `.stattxt` rules in charge of placement. The line sits in that row, inside the bar, and does not cover the interval labels. The bottom webview is refit to the row, then refit again when the next question removes it.
3. If the next card is not allowlisted, puts any counts the watcher already hid back onto **Show Answer** instead of deleting them.

`#new`, `#lrn`, and `#rev` are not in the 25.09+ reviewer. If a bottom bar still has them, they are concealed on the question and shown again on the answer. The ease buttons themselves are not rewritten, and the bottom bar HTML is not replaced.

An empty allowlist hides nothing. After a whitelisted card, the stock-mode script does run, so the next card's counts are put back if they were hidden. It does not hide counts on a deck that is not allowlisted. Bury, suspend, delete, undo, and skip can open the next question without an answer in between; the mode is updated from `card_will_show` before Anki redraws the bottom bar, and stock mode still restores counts if that redraw already hid them.

## Decks

**Tools → Hide Counts Until Answer: Choose Decks…** is the same dialog as the add-on **Config** button.

- The checklist saves `enabled_deck_ids`, plus the current names of those decks in `enabled_deck_names`.
- A parent id or parent name covers subdecks (`Med` covers `Med::Biochem`). Checking a parent does not also check every child, so a subdeck you add later is still covered.
- With nothing checked, counts stay visible everywhere.
- Filtered decks, including Free Review, are matched on the card's home deck: `odid` when Anki set it, otherwise `did`. The temporary filtered deck is not what the list stores.

`config.md` describes the same keys for the JSON editor. That editor is the fallback if the checklist cannot open.

## Anki versions

`min_point_version` is **250900** (Anki 25.09). The count markup above is the same in 25.09 and 26.09.3.

## Install

From a file. Anki reads `manifest.json` from the **root** of the zip and extracts those files into `addons21/hide_counts_until_answer/`:

```bash
./scripts/package_addon.sh
```

That writes `dist/hide_counts_until_answer.ankiaddon`. In Anki: **Tools → Add-ons → Install from file…**, then restart.

From a checkout, symlink the package folder (then restart):

```bash
# macOS
ln -s "$PWD/hide_counts_until_answer" ~/Library/Application\ Support/Anki2/addons21/hide_counts_until_answer

# Linux
ln -s "$PWD/hide_counts_until_answer" ~/.local/share/Anki2/addons21/hide_counts_until_answer
```

## Tests

```bash
python3 -m pip install -r requirements-dev.txt
python3 -m pytest
```

Headless. `aqt` is not imported. The suite checks:

- Shipped config is an empty allowlist, so counts are hidden nowhere.
- Config normalize drops junk ids and blank names and dedupes the rest.
- Ancestor names split on `::`. A parent id or parent name covers children. A lookalike name does not.
- Free Review / filtered cards use `odid` as the home deck when it is set, and `did` otherwise. A missing home deck hides nothing.
- The checklist checks exact ids and names, writes those ids, and keeps a covered child covered through the parent id.
- Question + allowlist is hide, answer + allowlist is show, anything else is stock. Leaving review restores.
- The bottom-bar script targets `.new-count`, `.learn-count`, and `.review-count`, and `#ansbut > span.stattxt`. It does not call `pycmd` or replace `#middle` HTML. On the answer, the parked `.stattxt` is mounted on an in-flow row above the ease buttons so Anki's own `.stattxt` rule places it. The script does not center that row on the interval labels and does not read `scrollHeight`.
- A whitelisted question followed immediately by another question (no answer in between) leaves that next card's counts visible. The markup is the Anki 25.09.2 reviewer bottom bar.
- `scripts/package_addon.py` builds an `.ankiaddon` with `zipfile`. The shell wrapper does not call the `zip` CLI.
