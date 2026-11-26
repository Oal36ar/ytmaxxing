# ytmaxxing brand: usage guide

**The idea: the highlighter.** ytmaxxing keeps the part of a video that's worth keeping, so the brand marks it the way you'd mark a book: one highlighter on plain paper.

**The mark: the XX ligature.** Two x's share their middle stroke. It reads as one mark and as the xx in "maxxing". It replaced the earlier red play-triangle mark on 26 Nov 2026, because a play triangle in red looked too close to YouTube, and ytmaxxing is independent.

## Files
| File | Use |
|---|---|
| `logo-mark.svg` | **Primary:** ink strokes on a highlighter square. README, social card, favicon |
| `logo-mark-inverse.svg` | **Inverse:** highlighter strokes on an ink square. Avatars, dark backgrounds |
| `logo-mark-black.svg`, `logo-mark-white.svg` | One colour, with the xx knocked out. Print and monochrome |
| `favicon.svg` | Browser tab (same as the primary) |
| `logo-primary.svg`, `logo-primary-dark.svg` | Lockup: mark + wordmark, on light or on its own dark tile |
| `logo-wordmark.svg` | Wordmark alone, with the xx highlighted |
| `png/logo-mark-{512,1024}.png`, `png/logo-mark-inverse-{512,1024}.png` | Raster marks, e.g. for avatars and the plugin icon |
| `../banner.html` → `../../assets/banner.png` (2560×840) | README header. Render at 1280×420 with a device scale factor of 2 |
| `../social.html` → `../../assets/social-preview.png` (1280×640) | GitHub social preview. Upload it in the repo's Settings → Social preview |

## Colours
| Name | Hex | Use |
|---|---|---|
| Paper | `#FBFAF6` | default background |
| Ink | `#111111` | text, the mark's strokes |
| Highlighter | `#E6FF3B` | the only accent: behind ink text, or as the mark's square. Never as text colour on Paper |
| Graphite | `#6B6A66` | secondary text |
| Rule | `#DCDAD3` | hairlines |

Contrast: ink on Paper is 18.1:1, ink on Highlighter is 16.8:1, and Graphite on Paper is 5.2:1.

## Type
**Familjen Grotesk** (weights 400–700, SIL Open Font License) for everything, and **Martian Mono** (OFL) for timestamps, commands and file names. No italics, nothing heavier than 700.

## Rules
- Highlight only what's being kept: at most one phrase per line.
- No gradients, glows, drop shadows or emoji icons. No YouTube red, and no play triangle.
- Minimum size: 16 px for the mark, 120 px wide for the lockup. Leave clear space of at least a quarter of the mark's width on every side.
- Don't rotate, skew, outline, stretch or recolour the mark.
