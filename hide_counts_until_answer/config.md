# Hide Counts Until Answer

On a whitelisted deck, the new / learning / review counts in the reviewer bottom bar are hidden on the question and shown again after the answer. Other decks keep stock Anki behavior. Nothing here changes scheduling.

An empty allowlist hides counts nowhere. That is the default.

## `enabled_deck_ids`

Deck ids saved by **Tools → Hide Counts Until Answer: Choose Decks…**, and by the add-on Config button (same checklist).

A parent id covers its subdecks. You do not need to list each child. Filtered decks, including Free Review, are matched on the card's home deck (`odid` when it is set, otherwise `did`), not on the temporary filtered deck id.

## `enabled_deck_names`

Optional exact deck names. A parent name such as `Parent` also covers `Parent::Child`. The checklist writes ids, and it rewrites this list to the current names of the decks you leave checked. Names still work if you edit them by hand and never open the checklist.

`Parent` does not match a different deck whose name merely contains that text.
