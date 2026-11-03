# The Kingdom: world notes for the map

Sources are the Ashfall Claude Docs: the Book 1 Greymark beat sheet, the Book 2 Valencourt beat sheet, the Book 2 beat sheet, the editor notes, and chapters IV–XI. They were read on 3 Nov 2026.

## Versions

- **3.0**: the current rewrite. I found no doc that literally says "3.0". The rewrite is the beat sheets: the Greymark act "keeps the v2.45 spine", and the Valencourt act is now the second half of Book 1 (Ch X–XXXIV).
- **v2.45**: the older draft. Drafted chapters IV–IX still follow it:
  - A river with an oily sheen.
  - A church on a boulder upstream.
  - A cave, an ossuary and a poison lake.
  - The angel as a crystal entity.
- **Old draft** places (Wilmsford, Harlow's Bridge, Odo, Halden) appear only in Ch XI "Winter Widow", which the Valencourt beat sheet says is replaced.

**Book 3.0 is the source of truth.** `data/story.json` holds its 60 events in order (Prologue → Greymark → Valencourt → Book 2). Where v2.45 differs, the event has a `v245` note, shown only when the **v2.45 ref** layer is on. v2.45-only places (the boulder church, the river cave, Wilmsford, Harlow's Bridge) are hidden by default and marked "v2.45" when shown.

## Placement: what the text says vs. what I guessed

| Place | Placement | Basis |
|---|---|---|
| Greymark | West, forested border town | "border town"; ledgers go "north" |
| Valencourt basin | South-east of Greymark, ringed by snowy peaks | "the warmth tugs south"; "a bowl of soft colour cupped between white peaks" |
| Wildling passes | North side of the ring | Wildlings "come over the mountain passes from the north" |
| Snowy plains | North, beyond the ring | "snowy plains beyond" the mountains |
| Annecy | South of the basin | "low country south of the basin" |
| Wilmsford (old) | Between Greymark and Valencourt | "4 days on foot", "last proper town before the river" |
| Greystone | West coast, grey beach | **Guess.** Only the rift-beach interior is described |
| Thornhearth | North | **Guess.** Only "has a guild" |
| House Aldric | North-east crag | **Guess.** Book 2 "road to House Aldric" |
| The Ashfall | Eastern Territories | **Guess.** The east is "more dangerous than the basin"; the womb's location is never given |

Every guessed place gets a **?** on its label. Move them in `map/world.js`.

## Kethric's route (the walking figure)

Wildling farm (prologue) → Greystone (the trio die) → Greymark → the young rift beneath it → Greymark → Valencourt → the wildling passes → House Aldric (Book 2).

## Open questions for you

- [ ] Does the kingdom have a name? The map title currently says "The Kingdom".
- [ ] Where is Greystone relative to Greymark? Is it coastal?
- [ ] Where is the Church's seat (where the ledgers go "north")?
- [ ] Where are Thornhearth and House Aldric?
- [ ] Where is the Ashfall itself? East is a guess.
- [ ] Where is Kethric's childhood valley (Merik's orphanage, The Wall)? Not on the map yet.
- [ ] Where did the book "3.0" and "2.45" files live (Word or Google Docs)? Only beat sheets and chapters were reachable here.

## Palette notes from the text

- **Greymark:** bone-white stone, dark timber, thatch, faint red water, autumn coming on.
- **Underground:** grey limestone turning red, orange cobbles.
- **Rifts:** black tears, red water, purple void crystal, blue-and-gold light (chalice and thurible).
- **Valencourt:** a warm green bowl with copper sheen, haze and white peaks; later its first snow.
- **Eastern Territories:** ash. This is inferred from the series name; no text describes it.
