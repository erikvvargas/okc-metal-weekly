# OKC Metal Weekly — v0.4

v0.4 is intentionally a **visual-only upgrade**. The Google Sheets workflow,
Friday–Thursday automatic week detection, and PowerShell wrapper from v0.3 all
continue to work the same way.

## What changed

- Added configurable **film grain** using procedural SVG noise.
- Added extremely subtle **horizontal/static scan texture**.
- Added a soft configurable **vignette**.
- OKC background images now get a stronger **photocopy / xerox treatment**:
  grayscale, contrast, brightness, and saturation are configurable.
- Week badge is now a slightly rotated **stamp** with a rough shadow.
- Kicker text has a tiny intentional rotation.
- Accent rules are slightly broken/distressed rather than perfectly clean.
- Venue names are now rendered as high-contrast white labels, closer to a
  pasted-up show flyer.
- Slides 2 and 3 no longer look identical:
  - Albums + EPs has a shorter rough rule and a giant faded `02` watermark.
  - Singles uses an inverted accent headline block and a giant faded `03`.
- Slide 4 is the most poster-like: the `OKC HEAVY` phrase is an angled accent
  stamp and the support blocks have slightly imperfect alignment.
- Page numbers are now accent-color labels rather than plain text.
- Existing custom-font support remains intact.

## Custom font setup

Put your downloaded font file in:

```text
static/fonts/
```

For example:

```text
static/fonts/Ashborn.ttf
```

Then edit `config.yaml`:

```yaml
typography:
  display_file: "Ashborn.ttf"
  condensed_file: ""
  body_file: ""
```

`display_file` controls the big poster headings such as `LIVE NOISE`,
`ALBUMS + EPS`, and `KEEP IT HEAVY`.

For readability, keep band names and venue listings on a condensed sans-serif.
If you also download Oswald, for example:

```yaml
typography:
  display_file: "Ashborn.ttf"
  condensed_file: "Oswald-Bold.ttf"
  body_file: "BarlowCondensed-Regular.ttf"
```

The generator will automatically use the fallback fonts when a configured font
file is missing.

## Most useful visual controls

All of these are in `config.yaml`.

### Overall color

```yaml
theme:
  active: "hazard_orange"
```

Available built-in palettes:

- `hazard_orange`
- `blood_red`
- `electric_blue`
- `ultraviolet`

You can also directly edit any palette hex values.

### Grain

```yaml
effects:
  grain:
    enabled: true
    opacity: 0.045
```

Recommended range: `0.025`–`0.075`.

If you immediately notice the grain, it is probably too strong.

### Static

```yaml
static:
  enabled: true
  opacity: 0.022
  line_spacing_px: 17
```

Recommended opacity: `0.01`–`0.035`.

### Vignette

```yaml
vignette:
  enabled: true
  opacity: 0.22
```

Try `0.12` for cleaner or `0.30` for dirtier.

### OKC photo treatment

```yaml
images:
  okc_background: "okc_skyline.jpg"
  okc_background_opacity: 0.24
  okc_grayscale: 1.0
  okc_contrast: 1.65
  okc_brightness: 0.56
  okc_saturation: 0.0
```

For an even harsher photocopy look, try:

```yaml
okc_contrast: 2.0
okc_brightness: 0.48
```

For a more photographic look:

```yaml
okc_contrast: 1.25
okc_brightness: 0.70
```

### Intentional imperfection / rotation

```yaml
rotations:
  enabled: true
  week_stamp_deg: 1.2
  kicker_deg: -0.45
  support_stamp_deg: -1.1
```

Keep these tiny. The goal is a pasted-up flyer, not visibly crooked design.

### Release-slide watermark

```yaml
release_watermark:
  enabled: true
  opacity: 0.05
```

Set it to `false` if you prefer the cleaner v0.3 release layout.

## Existing Google Sheets workflow

No changes. Normal run:

```powershell
.\generate-week.ps1
```

Forced week if your PowerShell wrapper supports it:

```powershell
.\generate-week.ps1 -Week 2026-09-11
```

The underlying Python command still supports:

```powershell
python generate.py --sheet-id YOUR_SHEET_ID --credentials .\service-account.json
```

## Recommended first test

1. Run v0.4 with your current color and OKC image.
2. Compare the four PNGs directly against v0.3.
3. Adjust only these three values first:
   - `grain.opacity`
   - `images.okc_background_opacity`
   - `images.okc_contrast`
4. Once those feel right, install your metal display font.

That keeps you from changing five visual variables at once.
