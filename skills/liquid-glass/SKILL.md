---
name: liquid-glass
description: Recreate the iOS 26 "liquid glass" refraction effect — real light bending through an SVG feDisplacementMap displacement field computed from Snell's law. Use when the user asks for glassmorphism, refraction, frosted glass, or a liquid-glass look in a web project.
---

# Liquid Glass (real refraction, not just blur)

The cheap "glass" everyone knows is `backdrop-filter: blur()`. Real liquid glass
(what iOS 26 does) **bends the light** behind the surface: near the rounded
corners the backdrop is displaced by a refraction profile, so anything behind
the glass visibly distorts around the edges — no blur, no tint, only bending.

## How it works

1. Model the rounded-corner profile as a convex squircle height map.
2. Refract a view ray through it with Snell's law → a displacement profile
   (how far the light bends vs. distance from the corner).
3. Paint that profile into a displacement map image: **R channel = dx,
   G channel = dy**, neutral = 128.
4. Feed the map to SVG `feDisplacementMap` and attach the filter to the glass
   element with `backdrop-filter: url(#id)`.
5. Add a small specular (edge highlight) map, masked to the corner band.

The working implementation lives in this repo: **`glass-calendar.html`** —
read `lgProfile`, `lgDispMap`, `lgSpecMap`, `lgFilterHtml`, and `lgRebuild`
there and copy them verbatim. The essential filter chain:

```html
<filter id="lg" x="0%" y="0%" width="100%" height="100%">
  <feImage href="DATA:URL" x="0" y="0" width="W" height="H" result="disp_map" />
  <feDisplacementMap in="SourceGraphic" in2="disp_map" scale="SCALE"
    xChannelSelector="R" yChannelSelector="G" result="displaced" />
  <feColorMatrix in="displaced" type="saturate" values="1" result="displaced_sat" />
  <feImage href="SPEC_DATA_URL" x="0" y="0" width="W" height="H" result="spec_layer" />
  <feComposite in="displaced_sat" in2="spec_layer" operator="in" result="spec_masked" />
  <feComponentTransfer in="spec_layer" result="spec_faded">
    <feFuncA type="linear" slope="0.45" />
  </feComponentTransfer>
  <feBlend in="spec_masked" in2="displaced" mode="normal" result="with_sat" />
  <feBlend in="spec_faded" in2="with_sat" mode="normal" />
</filter>
```

The displacement map is generated at runtime on a `<canvas>` for the element's
exact pixel size (the filter needs element-size maps, so rebuild on resize and
when the element's size changes — see `lgRebuild`).

## Wiring checklist

- Only Chromium desktop supports `backdrop-filter: url(#)`; gate it behind a
  UA check (`Chrome|Edg` and not mobile) adding a `.chromium` class.
- The glass element's `::before` (inset:0, border-radius = element radius)
  carries the `backdrop-filter: url(#filter-id)`.
- Put the `<defs id="lg-defs">` inside a zero-size inline SVG.
- Give the page a **visually rich backdrop** — the effect is only visible
  where light bends, and a flat background has nothing to bend. Photos,
  gradients with multiple stops, or soft color blobs all work.
- Merge filters into one defs book per element id (`lgCache`) and never
  overwrite the whole book with an empty string — filters for other elements
  would vanish.

## Tuning knobs (sweet spot shipped)

```js
const LG = { thickness:80, bezel:60, ior:3.0, scaleRatio:1.25, specOpacity:0.45 };
```

- `scaleRatio` = overall distortion strength. 0.2 = whisper-subtle; 1.25 = clear.
- `blur` (optional `feGaussianBlur` before displacement) = frost. 0 = pure refraction.
- `ior` = index of refraction (higher = bends more).
- `specOpacity` = edge highlight strength.
- Element radius should be ≥ 12px for the corner band to read.

## Two traps (we measured both — respect them)

1. **Animation `fill-mode: both` kills the refraction.**
   `animation: popIn .5s both` pins the element to its own compositor layer
   after the animation ends, and backdrop sampling gets clipped to the element
   bounds → the displacement map goes dead (even the blur dies). Never animate
   the glass element with fill-mode `both`. If you need an entrance animation,
   animate a wrapper or a non-backdrop property, or drop the fill mode.
2. **Displacement must stay ≤ 0.75 × element height.**
   The filter samples the backdrop within the element's region; displacement
   exceeding the element pulls sampling out of bounds. Measured: 0.72× works,
   0.75× works, 0.9× degrades to ~25% effective, ≥1× collapses the entire
   filter chain. After changing `scaleRatio`/size, verify the effective
   displacement = `maxDisp × scaleRatio` against the element height.

## Verification tip

A/B test with and without `backdrop-filter: url(#)` and pixel-diff the two
screenshots inside the page (canvas readback) — a healthy glass shows a
clear difference band along the corners. If the diff is ~0 with the filter
on, check trap 1 and trap 2 before touching anything else.
