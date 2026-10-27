# Design

`screens/` holds the English (default, LTR) screens; `arabic/` shows the same app in RTL.
They are reference mockups: match layout, hierarchy and tokens; data in them is invented.

| File | Screen |
|---|---|
| screens/Splash.png | Sign in |
| screens/Main.png | Home: receive / count tabs, open POs, sync state |
| screens/Receive.png | Receiving session: progress, scan field, filters, lines, toast with undo |
| screens/LineSheet.png | Line sheet: qty + UOM, expiry → auto batch, rejected qty |
| screens/ItemDetail.png | Item details with zoomable photo |
| screens/CountSetup.png | New count: type, entry method, scope, freeze |
| screens/Count.png | Blind count per batch, recount flag |
| screens/Review.png | Supervisor review in Desk |
| screens/BrandLogo.png, BrandSystem.png | Brand |

## Tokens

| Token | Value | Use |
|---|---|---|
| ink | #171717 | primary buttons, text |
| text-secondary | #525252 | labels |
| text-muted | #6B6B6B | meta (passes 4.5:1 on white) |
| surface | #FFFFFF | page |
| surface-2 | #F3F3F3 | inputs, subtle buttons |
| line | #EDEDED | dividers |
| brand-yellow | #F5B800 | logo stroke only |
| success | #15803D on #E8F7EE | complete |
| warning | #A14A05 on #FFF3E0 | over limit, offline, issues |
| danger | #B42318 on #FDECEC | late, errors |
| info | #0B5CAD on #EEF4FC | frozen, links |

- Radius 8px (inputs, buttons), 12px (image tiles), 16px (bottom sheets), pills 999px.
- Tap targets ≥ 44px. Scan field 44px with a 1.5px ink ring when focused.
- Type: Inter (Latin, numbers, tabular-nums for quantities), IBM Plex Sans Arabic (Arabic).
  Sizes 18/600 titles, 15/500 buttons, 14/400 body, 12/400 meta.
- Icons: Lucide, 1.5 stroke.
- One black button per screen. No gradients; only toasts get a soft shadow.

## Logo

`assets/logo.svg` (≥ 32px) and `assets/icon-small.svg` (< 32px, three heavier strokes).
Wordmark: "hasr", Inter 700, letter-spacing −0.045em. Arabic lockup: "حَصر" in IBM Plex Sans Arabic 700.
