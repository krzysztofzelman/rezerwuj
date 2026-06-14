---
name: bootstrap5-theme-rebrand
description: Rebrand a Bootstrap 5 application's full color system using CSS custom property overrides — primary, semantic accents (success/info/warning/danger), Flatpickr, icons, and metadata — without touching Bootstrap source
source: auto-skill
extracted_at: '2026-06-14T11:40:00.000Z'
---

# Bootstrap 5 Theme Rebrand via CSS Custom Properties

Use when rebranding a Bootstrap 5 application to a new color scheme. This approach overrides Bootstrap's built-in CSS custom properties in `:root` — no source file edits, no Sass rebuild needed.

## Core approach

Bootstrap 5 exposes its entire color system via CSS custom properties on `:root`. Override them in your own stylesheet (loaded **after** Bootstrap's CDN link) to instantly retheme the entire framework.

```css
/* app/static/css/style.css — loaded after Bootstrap CDN */

@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

:root {
    /* === Brand palette === */
    --bs-primary: #FF6B35;           /* main brand orange */
    --bs-primary-rgb: 255, 107, 53;  /* RGB values for rgba() usage */
    --bs-body-color: #2C3E50;        /* text color */
    --bs-body-bg: #ECF0F1;           /* page background */

    /* === Link colors === */
    --bs-link-color: #FF6B35;
    --bs-link-hover-color: #e55a2b;  /* slightly darker variant */

    /* === Emphasis (for badges, highlights) === */
    --bs-emphasis-color: #FF6B35;

    /* === Body font === */
    --bs-body-font-family: 'Inter', system-ui, -apple-system, sans-serif;
}
```

## What this covers

Setting these `:root` variables propagates to:

| Component | Effect |
|-----------|--------|
| `.btn-primary` | Background, border, hover, active states (Bootstrap uses `--bs-btn-bg`, `--bs-btn-hover-bg`, etc. referencing `--bs-primary`) |
| `.text-primary` / `.bg-primary` | Text and background colors |
| `a` / `a:hover` | Link colors (via `--bs-link-color`, `--bs-link-hover-color`) |
| `.badge bg-primary` | Badge backgrounds |
| `.border-primary` | Border color |
| `::selection` | Text selection highlight |
| Form inputs focus ring | `box-shadow` color |
| Pagination active items | Background and border |
| Nav active links | Text color and underline |

## Handling `.btn-outline-primary`

Bootstrap 5's `btn-outline-*` variants also use CSS custom properties, but they require explicit overrides because the outline variant uses a different set of properties:

```css
.btn-outline-primary {
    --bs-btn-color: #FF6B35;
    --bs-btn-border-color: #FF6B35;
    --bs-btn-hover-bg: #FF6B35;
    --bs-btn-hover-color: #fff;
    --bs-btn-hover-border-color: #FF6B35;
    --bs-btn-active-bg: #FF6B35;
    --bs-btn-active-color: #fff;
    --bs-btn-active-border-color: #FF6B35;
}
```

Without these, `.btn-outline-primary` will still use Bootstrap's default blue.

## Override all semantic colors, not just primary

A visually cohesive palette also requires overriding Bootstrap's **semantic accent colors** (`success`, `info`, `warning`, `danger`). Don't leave green `bg-success` badges clashing with your orange brand.

```css
:root {
    /* Brand palette */
    --bs-primary: #FF6B35;
    --bs-primary-rgb: 255, 107, 53;
    --bs-body-color: #2C3E50;
    --bs-body-bg: #ECF0F1;

    /* Semantic accents — tuned to match the warm orange brand */
    --bs-success: #E67E22;        /* warm orange-brown — replaces harsh green */
    --bs-success-rgb: 230, 126, 34;
    --bs-info: #3498DB;           /* blue — acceptable accent */
    --bs-info-rgb: 52, 152, 219;
    --bs-warning: #F1C40F;        /* yellow */
    --bs-warning-rgb: 241, 196, 15;
    --bs-danger: #E74C3C;         /* red */
    --bs-danger-rgb: 231, 76, 60;
}
```

This propagates to all `.bg-success`, `.text-success`, `.alert-success`, `.btn-success`, `.badge bg-success` across the entire app — no template edits needed.

### Color choice strategy

| Semantic | Recommended approach |
|----------|---------------------|
| `success` | Start with a **dark teal or muted green** — e.g., `#00897B` when primary is `#FF6B35`. Teal is complementary to orange on the color wheel, professional, and not eye-straining. **Avoid warm shades of the primary** (like `#E67E22` orange-brown) — users consistently reject them as "oczojebny" (eye-bleeding) because they blend confusingly with the primary. |
| `info` | Keep a neutral blue (`#3498DB`) — it's used sparingly and provides helpful contrast. |
| `warning` | Standard yellow/amber — doesn't clash with warm palettes. |
| `danger` | Standard red — doesn't clash. |

### When the user complains about the green

If the user says "oślepia ten kolor" / "oczojebny" (eye-bleeding) referring to green Bootstrap elements, they mean `--bs-success` (`#198754`, the default Bootstrap green). **Do NOT use a warm shade of the primary** (like `#E67E22` warm orange) — users will reject it as confusing/eye-bleeding. Instead use a **dark teal** that complements the primary without clashing:

```css
:root {
    --bs-success: #00897B;    /* dark teal — complementary to orange, not blinding */
    --bs-success-rgb: 0, 137, 123;
}
```

This also means the Flatpickr available-dates and any teal-toned elements should match the new success color family.

## Handling third-party date pickers (Flatpickr example)

Flatpickr's theme colors (today highlight, selected date) are set via direct color values in CSS, not custom properties. You must override them explicitly.

### Available / selected states

The `.flatpickr-day.available` class uses hardcoded green tones that match Bootstrap's old `--bs-success`. Update them to **teal tones** matching the new success palette (when primary is orange):

```css
/* Flatpickr — available dates (before: green tones; after: teal tones) */
.flatpickr-day.available {
    background: #d1f2eb !important;    /* light teal */
    border-color: #a3e4d7 !important;  /* medium teal */
    color: #0b5345 !important;         /* dark teal-green text */
    font-weight: 600;
    cursor: pointer !important;
}

.flatpickr-day.available:hover {
    background: #a3e4d7 !important;    /* medium teal on hover */
}

/* Flatpickr — today circle */
.flatpickr-day.today {
    border-color: #FF6B35 !important;  /* brand primary */
}

/* Flatpickr — selected date */
.flatpickr-day.selected,
.flatpickr-day.selected:hover {
    background: #FF6B35 !important;
    border-color: #FF6B35 !important;
}

Use `!important` sparingly — only for third-party components that set inline styles or have higher-specificity rules.

### Why Flatpickr available-dates matter

The `.flatpickr-day.available` selector controls how **selectable dates** appear in the calendar. If your custom CSS only overrides selected/today but leaves this as green `#d1e7dd`, it will clash with a warm brand palette. Always search for all Flatpickr color classes:

```bash
grep -r 'flatpickr' app/static/css/
```

## Updating the inline SVG favicon

If the app uses an inline SVG favicon (returned from a FastAPI/Flask endpoint), update the fill colors to match the new palette:

```python
# Before: #0d6efd (Bootstrap blue)
# After:  #FF6B35 (brand orange)

svg = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">
  <rect x="6" y="12" width="52" height="46" rx="6" fill="#FF6B35"/>
  <rect x="6" y="20" width="52" height="10" fill="#e55a2b"/>
  ...
</svg>"""
```

The color pair pattern:
- **Main shape**: brand primary (`#FF6B35`)
- **Accent/header**: darker variant (`#e55a2b`) — creates visual depth

## Process

### 1. Determine the new color palette

The user typically specifies 3 colors:
- **Primary** (brand accent): e.g., `#FF6B35`
- **Text**: e.g., `#2C3E50`
- **Background**: e.g., `#ECF0F1`

Derive from these:
- `--bs-primary-rgb`: convert hex to RGB (`#FF6B35` → `255, 107, 53`)
- `--bs-link-hover-color`: darken primary ~15-20% (or use a tool: `#FF6B35` → `#e55a2b`)
- `--bs-btn-hover-bg`: same as primary (Bootstrap handles hover internally)

### 2. Update the project's CSS file

Overwrite (or extend) the project's custom CSS file with the `:root` block above. Place the CSS `<link>` **after** the Bootstrap CDN `<link>` so the cascade takes effect.

### 3. Update the SVG favicon

If there's a `/favicon.ico` endpoint in `main.py` (or equivalent), update the SVG fill attributes. Keep the same SVG structure; only change color values.

### 4. Replace Bootstrap icons

When the brand changes, swap out Bootstrap Icons to match the new theme:

```html
<!-- Old -->
<i class="bi bi-shield-check"></i>

<!-- New — choose icons that match the new brand's theme -->
<i class="bi bi-check-circle"></i>
<i class="bi bi-wrench"></i>
<i class="bi bi-tools"></i>
<i class="bi bi-smartphone"></i>
<i class="bi bi-link"></i>
<i class="bi bi-wrench-adjustable"></i>
```

Grep for all existing icon classes before deciding what to replace:
```bash
grep -r 'bi bi-' app/templates/
```

### 5. Update app metadata

If the app has a title/description in the main application file (e.g., FastAPI's `title=` parameter), update it:

```python
app = FastAPI(
    title="naprawmnie — System Zleceń Serwisowych",
    description="SaaS do zarządzania zleceniami serwisowymi dla warsztatów naprawczych",
)
```

### 6. Fix duplicate HTML attributes found during edit

When editing templates, watch for existing broken markup — duplicate `style` attributes, mismatched tags, etc. Fix them as you go rather than leaving them for a separate cleanup pass.

### 7. Fix CSP if source maps are blocked

After deploying, the browser console may show CSP errors like:

```
Connecting to 'https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/js/bootstrap.bundle.min.js.map'
violates the following Content Security Policy directive: "connect-src 'self'".
```

Browsers request `.map` (source map) files via `connect-src`, not `script-src` or `style-src`. Add the CDN domain to the `connect-src` directive:

```python
# Before:
"connect-src 'self'; "

# After:
"connect-src 'self' https://cdn.jsdelivr.net;"
```

### 8. Verify visually

After deploying, check:
- Is every element that was previously blue now using the new brand color?
- Are `.btn-primary` hover/focus/active states correct?
- Are `.btn-outline-primary` hover/focus/active states correct?
- Is the favicon showing the new color?
- Are third-party components (date pickers, modals) correctly themed?

## What NOT to do

- **Do NOT edit Bootstrap's source files** — the `:root` override approach is cleaner and survives Bootstrap CDN version bumps.
- **Do NOT use `!important` on Bootstrap's own components (btn, badge, nav)** — the CSS custom property cascade handles them. Reserve `!important` for third-party widgets.
- **Do NOT set `--bs-primary` inside `.btn-primary`** — set it at `:root` and let Bootstrap's `--bs-btn-*` properties inherit from it.
- **Do NOT override every single component** — Bootstrap's built-in `--bs-*` → `--bs-btn-*` → component cascade handles most cases automatically.

## When to use this

- User says "change the theme colors" or "rebrand the app" with a new hex palette
- User provides a new primary color, text color, and background color
- The app uses Bootstrap 5 (loaded from CDN or bundled)
- The app has a custom CSS file that overrides Bootstrap defaults
- The app has an inline SVG favicon
