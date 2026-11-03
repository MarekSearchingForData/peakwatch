// The kingdom of Ashfall, as data. Edit this file to move things around.
//
// Coordinates are written as compass offsets {E, S} from the map centre
// (E = east, S = south; negatives are west/north). The isometric camera puts
// NORTH at the TOP of the screen, so the map reads like a normal map.
//
// `ver` tags where a place comes from:
//   '3.0'  = current rewrite (Book 1 Greymark/Valencourt beat sheets, Book 2 beat sheet)
//   '2.45' = older draft only (cut or replaced in 3.0)
//   'both' = present in both
// `pos` = how sure the placement is: 'text' (the book gives a direction),
//   'guess' (the book names it but never says where; placed for the map, change freely).
(function () {
  const C = 26; // grid is 52 x 52 tiles
  const g = (E, S) => ({ x: C + E + S, y: C + S - E });
  const at = (E, S, o) => Object.assign(g(E, S), o);
  const reg = (E, S, rx, ry, o) => Object.assign({ cx: C + E + S, cy: C + S - E, rx, ry }, o);

  const places = [
    // ---- prologue / Greystone ----
    at(-5, -14, { id: 'barn', name: 'The Wildling Farm', kind: 'battlefield', ver: 'both', pos: 'guess',
      book: 'Book 1 · Prologue', desc: 'The road with Ollen and the turnips, then the barn full of wildlings that explodes. Marin, Desso, Wren and Kethric fight here.' }),
    at(-16, 3, { id: 'greystone', name: 'Greystone', kind: 'rift', ground: 'sand', ver: 'both', pos: 'guess', size: 1.2, glow: '#6a8cff',
      book: 'Book 1 · memory', desc: 'Where Marin, Desso and Wren die. Kept offstage. Inside the rift: a long grey beach under endless twilight, a temple in crystal silk, the trio’s graves.' }),

    // ---- Greymark (3.0 layout: one water, one source — the well) ----
    at(-10, -6, { id: 'greymark', name: 'Greymark', kind: 'town', ver: 'both', pos: 'text', houses: { wall: '#cfc6b4', roof: ['#3a2a1e', '#5a4430'] },
      book: 'Book 1 · Ch I–IX', desc: 'Border town. Dark-timber palisade, thatched rows, bone-white stone gates. Hollow-eyed locals sign the Church’s ledger for cups of faintly red water.' }),
    at(-8, -2, { id: 'well', name: 'The Town Well', kind: 'well', ver: 'both', pos: 'guess',
      book: 'Book 1 · Ch I–III', desc: 'The water runs faintly red. Aldren’s priests pour, sign and carry, and never drink. Runs clear once the rift is closed.' }),
    at(-6, -9, { id: 'mill', name: 'Vex’s Linen Mill', kind: 'mill', ver: 'both', pos: 'guess',
      book: 'Book 1 · Ch II', desc: 'The town’s only real employer. Flax fields, blue coats and white jerkins, dye that won’t set. Eleven of Vex’s workers end up in the rift.' }),
    at(-13, -3, { id: 'compass', name: 'The Broken Compass', kind: 'tavern', ver: 'both', pos: 'guess', fx: { glow: true },
      book: 'Book 1 · Ch I', desc: 'Tavern with “Promise” carved over the door. Where Kethric drinks himself hollow months after Greystone.' }),
    at(-14, -7, { id: 'harren', name: 'Harren’s Cellar & the Ruin', kind: 'ruin', ver: '3.0', pos: 'guess', fx: { rift: false },
      book: 'Book 1 · Ch II–III', desc: 'Older stone under the town: a sealed stair, carvings Kethric can’t read, fresh tool marks. The ruin was a lid over a rift.' }),
    at(-14, -11, { id: 'youngrift', name: 'The Young Rift', kind: 'rift', ver: '3.0', pos: 'guess', size: 0.8,
      book: 'Book 1 · Ch III', desc: 'Small, dark, flooded. Warm red shallows, husks of the missing in rows. Kethric kills Aldren here, then angel-Vex, and takes the thurible.' }),
    at(-9, -12, { id: 'boulderchurch', name: 'Church on the Boulder', kind: 'church', ver: '2.45', pos: 'text',
      book: 'v2.45 · Ch IV–IX', desc: 'Old draft: the crystal angel waits in a church on a boulder upstream; Aldren fought there. Cut in 3.0 (replaced by the ruin and Harren’s cellar).' }),
    at(-16, 0, { id: 'cave', name: 'River Cave & Poison Lake', kind: 'ruin', ver: '2.45', pos: 'guess',
      book: 'v2.45 · Ch IV–V', desc: 'Old draft: boat landing among mossy boulders, limestone tunnel turning red, ossuary, treadwheels draining a poison lake, the eyeball-domed chapel.' }),

    // ---- the road south (old-draft towns) ----
    at(-5, 0, { id: 'harlow', name: 'Harlow’s Bridge', kind: 'gate', ver: '2.45', pos: 'guess',
      book: 'old draft · Ch XI', desc: 'Stone tollhouse checkpoint. Replaced in the rewrite.' }),
    at(-2, 5, { id: 'wilmsford', name: 'Wilmsford', kind: 'village', ver: '2.45', pos: 'text', houses: { roof: ['#2f3b52', '#46587a'] },
      book: 'old draft · Ch XI', desc: 'Slate roofs, the Gilded Sheaf inn, “last proper town before the river”. Four days on foot from Valencourt.' }),

    // ---- the Valencourt basin ----
    at(6, 6, { id: 'valencourt', name: 'Valencourt', kind: 'city', ver: '3.0', pos: 'text', roof: ['#5a3a20', '#b8742f'], flag: '#3a6fb0', fx: { tree: true },
      book: 'Book 1 · Ch X–XXXIV', desc: 'A warm bowl that “had never seen white”, heated by rift roots. House Deveraux’s keep on trapped ancient ruins, the Mother Tree in the square, vineyards, copper. Ends under first snow, a colossal tree over the city.' }),
    at(9, 8, { id: 'mothertree', name: 'The Mother Tree', kind: 'bigtree', ver: '3.0', pos: 'text',
      book: 'Book 1 · Valencourt', desc: 'Stands in the city square. Inside the rift\u2019s copy of the valley it is colossal, baobab-like, its roots grown through the keep: a spiral path, translucent veins, vats, a nursery of pods.' }),
    at(2, 3, { id: 'ravine', name: 'The Ravine', kind: 'camp', ver: '3.0', pos: 'guess',
      book: 'Book 1 · Valencourt', desc: 'Plateau over a ravine, stream below, birch trees and black soil.' }),
    at(10, 3, { id: 'mines', name: 'Copper Mines', kind: 'keep', ver: '3.0', pos: 'guess', stone: '#8a5c34', roof: ['#7a4a22', '#c07a3a'], flag: '#c07a3a',
      book: 'Book 1 · Valencourt', desc: 'Reopened copper mines. Ingots stamped with the Deveraux seal go out by caravan on the copper road.' }),
    at(3, 10, { id: 'palisade1', name: 'Basin Hamlet', kind: 'village', ver: '3.0', pos: 'guess',
      book: 'Book 1 · Valencourt', desc: 'One of the small towns on the basin edge: a little palisade and a feeble watchtower.' }),
    at(10, 9, { id: 'palisade2', name: 'Watchtower Hamlet', kind: 'village', ver: '3.0', pos: 'guess',
      book: 'Book 1 · Valencourt', desc: 'Basin-edge town with a feeble watchtower. Locals with French accents.' }),
    at(6, -3, { id: 'passes', name: 'The Wildling Passes', kind: 'marker', ver: '3.0', pos: 'text',
      book: 'Book 1 · Valencourt', desc: 'Wildlings in brown furs come over the mountain passes from the north.' }),
    at(6, 15, { id: 'annecy', name: 'Annecy', kind: 'village', ver: '3.0', pos: 'text',
      book: 'Book 1 · Valencourt', desc: 'Low country south of the basin. A caravan was hit near it.' }),

    // ---- the wider kingdom (named, unplaced in the text) ----
    at(2, -17, { id: 'thornhearth', name: 'Thornhearth', kind: 'town', ver: 'both', pos: 'guess', houses: { roof: ['#2f3b52', '#46587a'] },
      book: 'Book 1 · Ch II', desc: 'Has a guild. The town is told Vex was “sent to the guild in Thornhearth”. The old Book 2 plan went here.' }),
    at(11, -11, { id: 'aldric', name: 'House Aldric', kind: 'keep', ver: '3.0', pos: 'guess', stone: '#646c74', roof: ['#4a141c', '#7e2229'], flag: '#b8423a',
      book: 'Book 2', desc: 'Dragon-blood house. Its court mages, the Keepers of the Blood, are grey, quiet scholars. Book 2 opens on the road here.' }),
    at(17, 0, { id: 'ashfall', name: 'The Ashfall', kind: 'rift', ground: 'cinder', ver: '3.0', pos: 'guess', size: 1.7,
      book: 'Series', desc: 'The Never Born’s womb. Kethric carries two pieces of the Lady, so it will want him most. Placed in the Eastern Territories as a guess.' }),
  ];

  const regions = [
    // coastline handled by `coast`; regions paint over the land, later ones win
    reg(-11, -5, 9, 8, { t: 'forest', h: 2, hv: 1 }),                 // the dark forest around Greymark
    reg(-13, -9, 5, 4, { t: 'autumn', h: 2, hv: 1 }),                 // turning woods north-west
    reg(-6, -12, 5, 4, { t: 'autumn', h: 1, hv: 1 }),
    reg(-10, -6, 3.2, 3.2, { t: 'grass', h: 2, hv: 0, wobble: 0.2 }),  // town clearing
    reg(-7, -6, 2.5, 2, { t: 'meadow', h: 1, hv: 0 }),                 // flax fields by the mill
    reg(-16, 3, 3, 3, { t: 'sand', h: 1, hv: 0 }),                     // grey beach of Greystone
    reg(-3, 3, 6, 5, { t: 'grass', h: 1, hv: 1 }),                     // lowland road south
    reg(-8, 4, 5, 6, { t: 'forest', h: 1, hv: 1 }),                    // western woods
    reg(-1, -8, 4, 4, { t: 'forest', h: 2, hv: 1 }),
    reg(12, 14, 4, 3, { t: 'forest', h: 1, hv: 1 }),
    reg(-6, 9, 5, 4, { t: 'marsh', h: 1, hv: 0 }),                     // fen by the sea
    // mountain ring around Valencourt, then the warm basin inside it
    reg(6, 6, 12, 12, { t: 'stone', h: 4, hv: 3, snowAbove: 6, wobble: 0.35 }),
    reg(6, 6, 7.5, 7.5, { t: 'meadow', h: 2, hv: 1, wobble: 0.25 }),
    reg(9, 8, 3, 2.5, { t: 'autumn', h: 2, hv: 1 }),                   // vineyards / orchards
    reg(3, 4, 2.5, 2, { t: 'forest', h: 2, hv: 1 }),                   // birches over the ravine
    reg(6, -3, 2, 3, { t: 'snow', h: 4, hv: 1 }),                      // the pass
    // north: snowy plains the wildlings come from
    reg(4, -12, 9, 5, { t: 'snow', h: 2, hv: 1 }),
    reg(2, -17, 3, 3, { t: 'grass', h: 2, hv: 0 }),                   // Thornhearth's fields
    reg(11, -11, 3, 3, { t: 'stone', h: 3, hv: 1 }),                   // Aldric crag
    // south lowlands
    reg(6, 15, 5, 4, { t: 'meadow', h: 1, hv: 1 }),
    // the Eastern Territories: ash and cinder around the Ashfall
    reg(17, 0, 8, 10, { t: 'ash', h: 1, hv: 2, overSea: true }),
    reg(17, 0, 3.5, 3.5, { t: 'cinder', h: 1, hv: 1 }),
  ];

  const pts = (...a) => a.map(([E, S]) => { const p = g(E, S); return [p.x, p.y]; });
  const rivers = [
    { name: 'Greymark river', ver: '2.45', width: 1, pts: pts([-6, -15], [-9, -9], [-11, -2], [-14, 0], [-17, 6]) },
    { name: 'Ravine stream', ver: '3.0', width: 1, pts: pts([1, -1], [2, 4], [0, 8], [-4, 10], [-8, 12]) },
    { name: 'The red seep', ver: '3.0', t: 'blood', width: 1, pts: pts([-14, -11], [-12, -10], [-11, -8]) },
  ];

  const roads = [
    ['barn', 'greymark'], ['greymark', 'thornhearth'], ['greymark', 'greystone'],
    ['greymark', 'harlow'], ['harlow', 'wilmsford'], ['wilmsford', 'valencourt'],
    ['greymark', 'valencourt'], ['valencourt', 'annecy'], ['valencourt', 'passes'],
    ['valencourt', 'mines'], ['valencourt', 'palisade1'], ['valencourt', 'palisade2'],
    ['passes', 'aldric'], ['thornhearth', 'aldric'],
  ];

  // Kethric's journey in story order (3.0). Greymark → Valencourt is not
  // stated in the text; the beat sheet only says "the warmth tugs south".
  const route = ['barn', 'greystone', 'greymark', 'youngrift', 'greymark', 'valencourt', 'passes', 'aldric'];

  window.ASHFALL_WORLD = {
    title: 'The Kingdom',
    seed: 1337, w: 52, h: 52,
    coast: { cx: C + 2, cy: C - 3, rx: 25, ry: 27 }, // west and south-west fall away to the sea
    regions, rivers, roads, route, places,
    ashfall: 140,
  };
})();
