# ytmaxxing brand: usage guide (v2, the press look)

**The idea: the press.** ytmaxxing turns long videos into what's worth keeping, and the brand prints it: pictures are ASCII printed in ink on a card, every card is one of four colours, and the line people remember is set in a tall serif. v2 replaced the highlighter look (v1) on 27 Nov 2026.

**The mark: the XX ligature.** Two x's share their middle stroke. It reads as one mark and as the xx in "maxxing". It replaced the earlier red play-triangle mark on 26 Nov 2026, because a play triangle in red looked too close to YouTube, and ytmaxxing is independent.

## Files
| File | Use |
|---|---|
| `logo-mark.svg` | **Primary:** ink strokes on a stock square. README, favicon, light grounds |
| `logo-mark-inverse.svg` | **Inverse:** stock strokes on a cobalt square. Avatars, dark grounds |
| `logo-mark-orange.svg` | Ink strokes on an orange square. End cards and posters |
| `logo-mark-black.svg`, `logo-mark-white.svg` | One colour, with the xx knocked out. Print and monochrome |
| `favicon.svg` | Browser tab (same as the primary) |
| `logo-primary.svg`, `logo-primary-dark.svg` | Lockup: mark + plain wordmark, on light or on a cobalt tile |
| `logo-wordmark.svg` | Plain wordmark (no highlight) |
| `png/logo-mark{,-inverse,-orange}-{512,1024}.png` | Raster marks, e.g. for avatars and the plugin icon |
| `../banner.html` → `../../assets/banner.png` (2560×840) | README header |
| `../social.html` → `../../assets/social-preview.png` (1280×640) | GitHub social preview (Settings → Social preview) |
| `../render.py` | Renders the two images above and the PNG marks |
| `../../assets/research-hero.png` (2560×1440) | README Research section: the real thumbnails of the 15 videos in a real run, with a credit line. Built outside the repo, so the source thumbnails aren't redistributed here as separate files |

## Colours
| Name | Hex | Use |
|---|---|---|
| Stock | `#EEE9DD` | the default card |
| Cobalt | `#1E3BD9` | card; the serif and the ASCII ink on stock |
| Orange | `#F0642A` | card; on stock or cobalt only as the one accent (the star, one kept word) |
| Ink | `#151515` | text on stock and orange, hairlines, citation boxes |

Contrast: ink on stock 15.1:1, cobalt on stock 6.5:1, ink on orange 5.7:1. Orange on stock (2.6:1) is for the star and display-size words only. Never orange text on cobalt, never cobalt on orange.

## Type
**Instrument Serif** for the line people remember (display sizes only), **Familjen Grotesk** 700 capitals for facts and 400–500 for body and interface text, **Martian Mono** 500 for notes, timestamps, citations and commands. All SIL Open Font License. No italics.

## Rules
- One card per image or section; one orange accent per frame.
- Real pictures (screenshots, thumbnails) stay real; ASCII builds designed elements such as the mark (`../vendor/ascii-magic-art/`).
- The hand-drawn eight-stroke star is the series mark: a full stop or beside the wordmark, never inside the XX square.
- No highlighter, gradients, glows, drop shadows, purple or emoji icons. No YouTube red, and no play triangle.
- Minimum size: 16 px for the mark, 120 px wide for the lockup. Clear space of at least a quarter of the mark's width on every side.
- Don't rotate, skew, outline or stretch the mark; colour it only in the three pairs above.
