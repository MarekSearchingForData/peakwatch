# Art direction: getting past "blocks"

Researched 3 Nov 2026. Most links below were opened and their licences read. Prices marked unverified could not be checked.

**Why it looks like blocks:** the current map draws every building in code. Detail like the reference diorama (`reference/diorama-mood.jpg`) comes from hand-placed pixels: timber framing, thatch clusters, moss, barrels, lanterns. No procedural code gets there.

**The fix:** composite real pixel-art sprites (bought packs plus AI-drafted hero props), then hand-clean them. The engine, the story data and the city layouts stay. Only the drawing layer changes.

## References: what to look at

| Source | Why |
|---|---|
| Ultima Online (1997) | Closest match for Greymark: iso pixel medieval towns, timber and thatch, palisades, wells |
| [The Last Spell](https://lastspell.com/?p=1401) | Hand-pixelled iso dark-fantasy town under siege; same mood |
| Into the Breach | Clean, readable small iso buildings |
| Final Fantasy Tactics / Tactics Ogre | Props and character sprites |
| Age of Empires II / The Settlers II | Pre-rendered iso medieval buildings, the benchmark for a 3D-to-pixel route |
| [Pixel Joint](https://pixeljoint.com) (search "isometric"), r/PixelArt top posts, ArtStation "isometric pixel art medieval" | Mood-board browsing. Avoid AI-generated galleries |

**Tutorials**
- Slynyrd [Pixelblog 41: Isometric](https://www.slynyrd.com/blog/2022/11/28/pixelblog-41-isometric-pixel-art) and [Pixelblog 54: More isometric](https://www.slynyrd.com/blog/2025/1/23/pixelblog-54-isometric-pixel-art)
- AdamCYounis (YouTube): isometric tile basics and isometric character basics
- [Saint11 mini-tutorials](https://saint11.art/blog/pixel-art-tutorials/) for materials and light

## Asset packs (32px, true 2:1 isometric, so they mix)

| Pack | Price | Licence | Gives us |
|---|---|---|---|
| [Zato: Isoverse Medieval Outdoors](https://zatoart.itch.io/isoverse-medieval-outdoors) | $7.50 | Commercial OK, credit "Asset by Zato", no redistribution, no AI training | **Best fit.** 135 modular buildings, walls, towers, market stalls, lamps, trees |
| [Zato: Isometric Isolation](https://zatoart.itch.io/isometric-isolation) | $4 | Same terms (the free tier is non-commercial) | Village, castle and forest tiles |
| [Kelano: Medieval Buildings Pack](https://kelano-studio.itch.io/medieval-buildings-pack) | $5 | Commercial OK, no credit needed, no redistribution | 30 houses, churches and military buildings (64px) |
| [KipperFalcon: Isometric Forest](https://kipperfalcon.itch.io/2d-isometric-forest-pixel-art) | free | CC0 art, but the author asks for no redistribution and no AI training | Trees, rocks, grass |
| [Xilurus: Pixel Isometric Village](https://xilurus.itch.io/pixel-isometric-village) | free | Commercial OK, no resale | 150+ village tiles (16px) |
| [OGA: CC0 isometric](https://opengameart.org/content/cc0-isometric) | free | CC0 | Blender-rendered buildings and props; good for blocking out |

**Repo rule:** paid packs must not be committed to a public repo, because that counts as redistribution. Keep them in a git-ignored `assets/vendor/` folder.

**No pack has:** the red-water well, Vex's linen mill, the dark-timber palisade with bone-white gates, the mossy ruin, or animated fire and water. Those are hero props we make ourselves.

## Tools for the hero props

| Tool | Cost | Notes |
|---|---|---|
| [Retro Diffusion](https://github.com/Retro-Diffusion/api-examples) | Prepaid credits from $5. Isometric styles cost $0.06–0.18 per image | States that all output can be used commercially. Has an API and an MCP server, so I can drive it from here once you add a key |
| [PixelLab](https://www.pixellab.ai) | About $9–12/month (unverified) | Has isometric tile and map-object endpoints and an [official MCP server](https://github.com/pixellab-code/pixellab-mcp). You own the outputs; you may not train models on them |
| [Aseprite](https://www.aseprite.org) | $19.99 | Required: clean up every AI or pack sprite here (palette, edges, light) |
| [PixelOver](https://pixelover.io) | $19.99 | 3D-to-pixel with palette, dither and outlines |
| [Pixel Composer](https://makham.itch.io/pixel-composer) | $15+ | Animated fire, water and smoke loops |
| Blender | free | Orthographic 2:1 render at final pixel size, then a paint-over. Gives the most consistent buildings |

**AI caveats:**
- Angle, pixel size and palette drift between images.
- Buildings come out mushy.
- Plan to clean up every keeper by hand.
- Never feed the no-AI-training packs (Zato, KipperFalcon, BoostyBear) to a model, even as a style reference.

## Recommended route: one Greymark diorama at reference quality

1. **Base kit (about $17):** Zato Isoverse + Isometric Isolation, plus the free KipperFalcon forest. Recolour everything to one dark-autumn palette.
2. **Hero props (about $10–20):** draft the well, mill, palisade, tavern sign and ruin arch with Retro Diffusion, then paint over them in Aseprite.
3. **The scene:** a hexagonal floating slab like the reference, composed in Tiled or straight in our engine as sprites. Show the square at dusk: Aldren at the well, the Broken Compass, the mill wheel, lanterns.
4. **Animation:** 4–6 frame loops for fire, lanterns and the well shimmer.

**Total:** about $55–90 including Aseprite, plus 2–4 days of cleanup.

The big city plans stay as the overview and navigation map. The detailed dioramas are where the story is told.
