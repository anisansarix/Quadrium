/* Hallmark · macrostructure: Bento Grid · H1 hero knobs: ratio=N/A, divider=hairline
 * theme: studied-DNA (source: image) · paper oklch(98% 0 0) · accent green (vibrant)
 * display: neutral grotesque (Inter candidate) · body: neutral grotesque (Inter candidate) · label: mono (Geist Mono candidate)
 * studied: yes · DNA-source: image (user-attached)
 */

# Design — Quadrium

Locked design system. Future Hallmark runs read this file first; pages defer
to it. Amend intentionally — the file is the rule.

## Provenance
Extracted from image (user-attached) — user-owned source, 2026-09-23.
Tokens are estimated from source-image colour bands. Fonts are role-based with named candidates from the Hallmark canon. Rhythm is from a vision pass on the source.

## System
- Genre · modern-minimal
- Macrostructure · Bento Grid
- Theme · studied-DNA
- Axes · light / grotesque-sans / green

## Tokens (canonical · `tokens.css` is the source of truth)
```css
:root {
  --color-paper:      oklch(98% 0 0); /* Light mode */
  --color-paper-2:    oklch(95% 0 0);
  --color-ink:        oklch(15% 0 0);
  --color-ink-2:      oklch(40% 0 0);
  --color-rule:       oklch(90% 0 0);
  --color-accent:     oklch(75% 0.15 150); /* Vibrant green */
  --color-accent-ink: oklch(98% 0 0);
  --color-focus:      oklch(75% 0.15 150);

  /* Dark mode variants (implied by source) */
  --color-paper-inverse:   oklch(15% 0 0);
  --color-ink-inverse:     oklch(95% 0 0);
  --color-rule-inverse:    oklch(30% 0 0);

  --font-display: "Inter", system-ui, sans-serif;
  --font-body:    "Inter", system-ui, sans-serif;
  --font-mono:    "Geist Mono", monospace;

  /* 4-pt spacing scale, named: --space-3xs … --space-4xl. See tokens.css.   */
  /* Type scale, 1.25 (major-third) ratio: --text-xs … --text-display.       */

  --ease-out: cubic-bezier(0.16, 1, 0.3, 1);
  --dur-fast: 180ms;  --dur-base: 240ms;  --dur-slow: 320ms;

  --radius-card: 8px;  --radius-pill: 999px;  --radius-input: 6px;
}
```

## CTA voice
- Primary · vibrant green fill · 6px radius · dense utilitarian padding (e.g. 8px 16px)
- Secondary · outline / ghost · 6px radius

## Motion stance
- motion-cut (utilitarian / component showcase style)
- Reduced-motion fallback · ≤150 ms opacity crossfade.

## Notes
- **Anti-patterns to NOT carry over:** No bouncy hovers, no transition-all. Keep interactions crisp and instantaneous.
- **Key treatments:** 1px hairline borders on cards, subtle shadows on light mode, extremely clean modular spacing, vibrant accent color sparingly used for primary actions and data highlights.

## Exports
`tokens.css` (in this project) is the source of truth. For Tailwind v4
`@theme`, DTCG `tokens.json`, or shadcn/ui CSS variables, ask *"extend
design.md with Tailwind exports"* (or the format you want) — Hallmark will
append them per `export-formats.md`.
