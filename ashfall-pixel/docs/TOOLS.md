# Toolchain research — isometric pixel-art animated story

Researched November 2026. **[verified]** means the version or price was checked on the official page. Everything else came from search results or memory, so confirm it before buying.

## Recommended stack

| # | Tool | Role | Cost |
|---|---|---|---|
| 1 | [Aseprite](https://www.aseprite.org) | Sprites, tiles, animation, sheet export (CLI) | $19.99 one-time **[verified]** |
| 2 | [Tiled 1.12](https://www.mapeditor.org) | Isometric, staggered and **hex** maps; JSON export from the CLI | Free (GPL) **[verified]** |
| 3 | [Phaser 4](https://phaser.io) | Web runtime: iso tilemaps, tweens, cutscenes | Free (MIT) **[verified 4.1.0]** |
| 4 | [Ink + inkjs](https://www.inklestudios.com/ink) | Story and dialogue; tags drive scene actions | Free (MIT) |
| 5 | [Resurrect 64](https://lospec.com/palette-list/resurrect-64) palette | Ember, ash and moss ramps for the whole project | Free **[verified]** |

Optional: [PixelLab](https://www.pixellab.ai) for draft isometric tiles and walk cycles. It has an API and an MCP server.

**Runner-up engine:** [Godot 4.7](https://godotengine.org) (free) if you want a visual scene editor. It has isometric and hex TileMapLayer, AnimationPlayer for cutscenes and 2D lights. The web build is about 30–40 MB and must use GDScript, not C#.

## What's in this folder now

The kingdom map (`map/`) is a **zero-dependency canvas prototype**: plain JS, no build step. Map data lives in `world.js`, so moving a town is a one-line edit. It is a sandbox for the art direction and the geography. The full story will move to Phaser and Tiled.

## Everything considered

### Pixel and animation editors
- **Aseprite**: the industry standard. Onion skin, tags, tilemap mode, Lua, CLI (`aseprite -b x.aseprite --sheet out.png --data out.json --list-tags`). The trial can't save, so it's no use headless.
- **Pixelorama**: free (MIT), has an isometric grid and tilemap layers. The best free alternative.
- **LibreSprite**: free fork of old Aseprite. No tilemap mode.
- **Piskel**: browser-based, fine for quick tests.
- **Pyxel Edit**: development has stalled. Skip it.
- **PixelOver** ($19.99, Early Access): bone animation and 3D-to-pixel. Gives smooth walk cycles without redrawing every frame.

### Isometric maps and 3D-to-pixel
- **Tiled**: supports isometric, staggered and hex maps. It fits the hexagon diorama in the reference image (`reference/diorama-mood.jpg`).
- **LDtk**: no isometric support (the site says so). **Sprite Fusion**: found no isometric support either.
- **Blender**: render an orthographic camera at 30°/45° to a small size, scale nearest-neighbour, then quantise to the palette. This is the most reliable route to 8-direction characters. **MagicaVoxel** (free) and **Crocotile 3D** (about $30) suit props and buildings.

### Engines
| Engine | Verdict |
|---|---|
| Phaser 4 | **Pick.** Web-native and all text/JS, so easy to automate. Supports iso, staggered and hex tilemaps. |
| Godot 4.7 | Runner-up. Best if you want an editor GUI. |
| PixiJS v8 | Renderer only; you'd write iso sorting yourself. |
| Excalibur | Has IsometricMap, but no staggered or hex Tiled maps. |
| Ren'Py 8.5 | Good for dialogue-heavy visual-novel chapters, poor for walking through dioramas. |
| GB Studio / RPG Maker / Unity | No isometric, or too heavy for the web. |

### Narrative
- **Ink / inkjs 2.3**: lines carry tags (`# walk:kethric:well`, `# camera:greymark`) that a Phaser "director" turns into actions.
- **Yarn Spinner 3**: fine, but the Godot port is pre-release. **Dialogic 2**: still alpha. **Twine**: useful for sketching branches.

### AI-assisted pixel art: use for drafts only
- PixelLab (subscription, about $10–12/mo) and Retro Diffusion ($65 one-time Aseprite extension, or web credits). Hugging Face pixel-art LoRAs carry model-specific, often non-commercial licences.
- **Caveats:**
  - The output is not true pixel art: mixed pixel sizes, stray colours.
  - Characters drift between frames.
  - The angle is often not a true 2:1 isometric.
  - Purely AI-generated images may not be copyrightable.
- Always downscale nearest-neighbour, quantise to the palette and hand-clean.

### Palettes ([Lospec](https://lospec.com/palette-list))
Resurrect 64 (main), Apollo (muted autumn), Endesga 32 (vivid), and the `autumn` and `darkfantasy` tags for mood studies.

### Placeholder assets
[Kenney](https://kenney.nl/assets) isometric packs (CC0) are good for blocking out layouts. itch.io and OpenGameArt licences vary, so log every one in a `CREDITS.md`.

### Headless helpers (Linux, usable by an AI agent)
- **Python Pillow / numpy**: palette checks, quantising, slicing (installed here).
- **ImageMagick**: `convert in.png -filter point -resize 400% -remap palette.png out.png` (installed).
- **ffmpeg**: GIF and MP4 export of animations (installed; used by `tools/render.mjs`).
- **Playwright + Chromium**: headless screenshots and frame capture (installed).
- **free-tex-packer-cli**: sprite atlases for Phaser.
- **Tiled**: `tiled --export-map json in.tmx out.json`.
- **Godot**: `godot --headless --export-release Web`.

## Pipeline

1. **Concept**: thumbnail each diorama. Fix the projection at **2:1 isometric, 16×8** (map) and 32×16 (scenes).
2. **Palette**: lock Resurrect 64 or a 32-colour subset. A Pillow check fails any off-palette pixel.
3. **Tiles**: ground, cliff, water and ash sets in Aseprite on an iso grid, exported with the CLI.
4. **Characters**: Kethric, Vex, Aldren and others with idle, walk and talk in 4 or 8 directions, tagged in Aseprite and packed to JSON atlases.
5. **Map assembly**: Tiled layers (ground, props, Y-sorted objects, paths), exported to JSON.
6. **Scenes and dialogue**: Ink script, where tags drive walks, camera pans, fades and ember particles.
7. **Web export**: Vite build to a static site (GitHub Pages or itch.io). CI rebuilds atlases, maps and Ink.
