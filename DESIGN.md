# ShadowDrive Design System

## Color Tokens

All colors defined as Tailwind v4 custom properties in `shadowdrive-ui/src/index.css` under `@theme`. Uses a dark-first palette with emerald primary and natural warm neutrals.

| Token | Value | Usage |
|---|---|---|
| `--color-primary` | `#4edea3` | Primary brand color |
| `--color-primary-fixed` | `#6ffbbe` | Primary in light mode (fixed) |
| `--color-primary-fixed-dim` | `#4edea3` | Dimmed primary fixed variant |
| `--color-primary-container` | `#10b981` | Container background for primary surfaces |
| `--color-on-primary` | `#003824` | Text/icon on primary |
| `--color-on-primary-fixed` | `#002113` | Text on primary fixed |
| `--color-on-primary-fixed-variant` | `#005236` | Variant text on primary fixed |
| `--color-on-primary-container` | `#00422b` | Text on primary container |
| `--color-secondary` | `#68dba9` | Secondary accent color |
| `--color-secondary-fixed` | `#85f8c4` | Secondary in light mode (fixed) |
| `--color-secondary-fixed-dim` | `#68dba9` | Dimmed secondary fixed variant |
| `--color-secondary-container` | `#25a475` | Container background for secondary |
| `--color-on-secondary` | `#003825` | Text on secondary |
| `--color-on-secondary-fixed` | `#002114` | Text on secondary fixed |
| `--color-on-secondary-fixed-variant` | `#005137` | Variant text on secondary fixed |
| `--color-on-secondary-container` | `#00311f` | Text on secondary container |
| `--color-tertiary` | `#ffb3af` | Tertiary accent (warm coral) |
| `--color-tertiary-fixed` | `#ffdad7` | Tertiary in light mode (fixed) |
| `--color-tertiary-fixed-dim` | `#ffb3af` | Dimmed tertiary fixed variant |
| `--color-tertiary-container` | `#fc7c78` | Container background for tertiary |
| `--color-on-tertiary` | `#650911` | Text on tertiary |
| `--color-on-tertiary-fixed` | `#410005` | Text on tertiary fixed |
| `--color-on-tertiary-fixed-variant` | `#842225` | Variant text on tertiary fixed |
| `--color-on-tertiary-container` | `#711419` | Text on tertiary container |
| `--color-background` | `#131313` | Page background |
| `--color-on-background` | `#e5e2e1` | Text on background |
| `--color-surface` | `#131313` | Default surface |
| `--color-surface-dim` | `#131313` | Dim surface |
| `--color-surface-bright` | `#3a3939` | Bright surface variant |
| `--color-surface-tint` | `#4edea3` | Surface tint (primary) |
| `--color-surface-variant` | `#353534` | Surface variant |
| `--color-surface-container-lowest` | `#0e0e0e` | Lowest elevation container |
| `--color-surface-container-low` | `#1c1b1b` | Low elevation container |
| `--color-surface-container` | `#201f1f` | Default elevation container |
| `--color-surface-container-high` | `#2a2a2a` | High elevation container |
| `--color-surface-container-highest` | `#353534` | Highest elevation container |
| `--color-on-surface` | `#e5e2e1` | Text on surface |
| `--color-on-surface-variant` | `#bbcabf` | Variant text on surface |
| `--color-inverse-surface` | `#e5e2e1` | Inverse surface (for light modals) |
| `--color-inverse-on-surface` | `#313030` | Text on inverse surface |
| `--color-inverse-primary` | `#006c49` | Inverse primary |
| `--color-outline` | `#86948a` | Outline borders / dividers |
| `--color-outline-variant` | `#3c4a42` | Variant outline color |
| `--color-error` | `#ffb4ab` | Error states |
| `--color-error-container` | `#93000a` | Error container background |
| `--color-on-error` | `#690005` | Text on error |
| `--color-on-error-container` | `#ffdad6` | Text on error container |

## Typography

### Font Families

| Token | Font stack | Usage |
|---|---|---|
| `--font-family-sans` | `"Geist", system-ui, sans-serif` | Default sans-serif |
| `--font-family-mono` | `"JetBrains Mono", monospace` | Default monospace |
| `--font-family-body-lg` | `"Geist", sans-serif` | Large body text |
| `--font-family-body-md` | `"Geist", sans-serif` | Medium body text |
| `--font-family-display-lg` | `"Geist", sans-serif` | Large display headlines |
| `--font-family-headline-md` | `"Geist", sans-serif` | Medium headlines |
| `--font-family-headline-lg` | `"Geist", sans-serif` | Large headlines |
| `--font-family-headline-lg-mobile` | `"Geist", sans-serif` | Large headlines (mobile) |
| `--font-family-label-md` | `"JetBrains Mono", monospace` | Medium labels / badges |
| `--font-family-code-sm` | `"JetBrains Mono", monospace` | Small code |

### Text font stack

- **"Geist"** for body, display, headline text
- **"JetBrains Mono"** for code, label, and badge text

### Type Scale

| Token | Size | Weight | Line Height | Letter Spacing |
|---|---|---|---|---|
| `display-lg` | 48px | 700 | 1.1 | -0.02em |
| `headline-lg` | 32px | 600 | 1.2 | -0.01em |
| `headline-lg-mobile` | 28px | 600 | 1.2 | — |
| `headline-md` | 24px | 600 | 1.3 | — |
| `body-lg` | 18px | 400 | 1.6 | — |
| `body-md` | 16px | 400 | 1.6 | — |
| `label-md` | 14px | 500 | 1.4 | 0.02em |
| `code-sm` | 12px | 400 | 1.4 | — |

## Components

### Button

A versatile action button with loading state, icon support, and four visual variants.

**Props:**

| Prop | Type | Default | Description |
|---|---|---|---|
| `variant` | `'primary' \| 'secondary' \| 'ghost' \| 'danger'` | `'primary'` | Visual style |
| `size` | `'sm' \| 'md' \| 'lg'` | `'md'` | Button size |
| `loading` | `boolean` | `false` | Shows a spinner and disables |
| `icon` | `string` | — | Material Symbol name for leading icon |
| `children` | `ReactNode` | — | Button label content |
| `disabled` | `boolean` | — | Native disabled attribute (inherited from `ButtonHTMLAttributes`) |

**Variants:**

- **primary:** Solid emerald background with glow shadow
- **secondary:** Outlined with primary border, fills on hover
- **ghost:** Transparent, text appears on hover
- **danger:** Error-colored text with subtle border

All variants use `rounded-lg` and `transition-all duration-300`.

---

### Card

A flexible container with glass, bordered, and elevated options, plus hover lift and glow effects.

**Props:**

| Prop | Type | Default | Description |
|---|---|---|---|
| `variant` | `'glass' \| 'glass-darker' \| 'bordered' \| 'elevated'` | `'glass'` | Surface treatment |
| `hover` | `boolean` | `false` | Enables hover lift & border brightening |
| `glow` | `'primary' \| 'error' \| 'none'` | `'none'` | Glow shadow color |
| `children` | `ReactNode` | required | Card content |
| `className` | `string` | `''` | Additional classes |

**Variants:**

- **glass:** Semi-transparent panel with `blur(20px)` backdrop
- **glass-darker:** Darker variant of glass panel
- **bordered:** Low-opacity border on dim surface
- **elevated:** Filled surface with subtle border and `shadow-lg`

**Hover:** `hover:translate-y-[-2px]`, `hover:border-white/20`, `hover:shadow-[...]` with `transition-all` on the container.

All variants use `rounded-xl`.

---

### Modal

A centered overlay dialog with backdrop blur, Escape-to-close, and optional title, footer, and three width tiers.

**Props:**

| Prop | Type | Default | Description |
|---|---|---|---|
| `open` | `boolean` | required | Visibility control |
| `onClose` | `() => void` | required | Close handler |
| `title` | `string` | — | Optional header title |
| `children` | `ReactNode` | required | Modal body content |
| `footer` | `ReactNode` | — | Optional action bar at the bottom |
| `maxWidth` | `'sm' \| 'md' \| 'lg'` | `'md'` | Width constraint |

**maxWidth values:**

- **sm:** `max-w-sm` (384px)
- **md:** `max-w-md` (448px)
- **lg:** `max-w-4xl` (896px)

Closes on backdrop click and Escape key. Panel uses `glass-panel-darker` styling with `rounded-xl` and `shadow-2xl`.

---

### PageHeader

A top bar with blur backdrop, breadcrumb-style icon+title, and an actions slot. Used across dashboard pages.

**Props:**

| Prop | Type | Default | Description |
|---|---|---|---|
| `icon` | `string` | — | Material Symbol name for leading icon |
| `title` | `string` | required | Header label (uppercased) |
| `iconColor` | `string` | `'text-primary'` | Tailwind text color class for icon |
| `actions` | `ReactNode` | — | Action buttons / controls slot |

Styled via the `.page-header` utility class: `h-20`, `border-b border-white/5`, blur backdrop, `px-margin-desktop`.

---

### EmptyState

A centered placeholder for empty lists or no-results states, with icon, title, description, and optional action slot.

**Props:**

| Prop | Type | Default | Description |
|---|---|---|---|
| `icon` | `string` | required | Material Symbol name |
| `title` | `string` | required | Heading text |
| `description` | `string` | required | Supporting text |
| `action` | `ReactNode` | — | Call-to-action element |

Layout: centered column with `py-24`, the icon sits in a bordered circle (`w-16 h-16`), followed by `headline-sm` title, `code-sm` description, and optional action below.

---

### Badge

A small numeric count indicator with four color variants. Renders `null` when `count <= 0`.

**Props:**

| Prop | Type | Default | Description |
|---|---|---|---|
| `count` | `number` | required | Number to display |
| `variant` | `'error' \| 'warning' \| 'primary' \| 'default'` | `'default'` | Color variant |
| `className` | `string` | `''` | Additional classes |

**Variants:**

- **error:** Error container background, error border glow
- **warning:** Yellow-500 tint with yellow border
- **primary:** Primary tint with primary border
- **default:** White/10 background, surface-variant text

Uses `rounded-full`, `text-xs`, `font-code-sm` sizing.

---

## Layout

- **Max container width:** Not explicitly theme'd — uses Tailwind default container or custom `max-w-*` per page
- **Desktop margin:** `48px` (`--spacing-margin-desktop`)
- **Mobile margin:** `16px` (`--spacing-margin-mobile`)
- **Gutter:** `24px` (`--spacing-gutter`)
- **Unit:** `4px` (`--spacing-unit`)
- **Border radius default:** `0.125rem` (`--radius`)
- **Border radius lg:** `0.25rem` (`--radius-lg`)
- **Border radius xl:** `0.5rem` (`--radius-xl`)

---

## Motion

### Transition Patterns

| Pattern | Used In | Details |
|---|---|---|
| `transition-colors` | Button (primary, ghost, danger), PageHeader close btn, Card (hover) | Smooth color/tint changes |
| `transition-all` | Button (secondary), Card (hover) | Multi-property transitions |
| `transition-all duration-300` | Button (all variants) | Standard 300ms easing |
| `transition-transform` with `ease-out` | Tilt card, feature card reveal | Fast 150ms transform on interaction |
| `cubic-bezier(0.16, 1, 0.3, 1)` | Scroll reveal animations | Custom ease-out spring |
| `opacity 0.8s ... transform 0.8s ...` | `reveal-up`, `feature-card-reveal` | Entry animations on scroll |

### Loading Spinner

Used in `Button` when `loading=true`:
```tsx
<span className="w-4 h-4 border-2 border-current border-t-transparent rounded-full animate-spin" />
```

### Hover Effects

- `hover:bg-white/5` — Ghost Button, PageHeader close button
- `hover:text-primary` — Ghost Button, PageHeader close button
- `hover:bg-primary-container` — Primary Button
- `hover:bg-primary` / `hover:text-surface-container-lowest` — Secondary Button
- `hover:bg-error/10` — Danger Button
- `hover:border-white/20` — Card hover
- `hover:translate-y-[-2px]` — Card hover lift
- `hover:shadow-[0_10px_30px_-10px_rgba(0,0,0,0.5)]` — Card hover shadow
- `hover:shadow-[0_0_20px_rgba(16,185,129,0.4)]` — Button glow expansion

### Glow & Pulse Animations

| Name | Details | Usage |
|---|---|---|
| `shimmer` | `5s linear infinite` diagonal gradient sweep | `emerald-text-glow` class |
| `pulse-emerald` | `2s infinite` box-shadow ring expansion | `.animate-pulse-emerald` |
| `pulse-dot` | `2s infinite` primary-colored pulse ring | `.pulse-dot` |
| `float` | Random translate + scale oscillation | Floating background orbs |
| `topology-pulse` | `3s infinite` scale + opacity + drop-shadow | `.topology-icon` |
| `input-glow` | `0 0 15px rgba(16, 185, 129, 0.3)` on `:focus` | Auth input focus ring |

### Entry / Scroll Animations

- `.reveal-up` — 30px translateY upward with 0.8s cubic-bezier, activates via `.is-visible`
- `.feature-card-reveal` — 32px translateY upward with 0.7s cubic-bezier, activates via `.is-active`, includes hover glow on `box-shadow` and `border-color`

---

## Glass & Surface Utilities

| Class | Background | Backdrop | Border |
|---|---|---|---|
| `.glass-panel` | `rgba(17,17,17,0.6)` | `blur(20px)` | `1px solid rgba(255,255,255,0.1)` |
| `.glass-panel-darker` | `rgba(17,17,17,0.8)` | `blur(20px)` | `1px solid rgba(255,255,255,0.1)` |
| `.liquid-glass` | `rgba(255,255,255,0.01)` with blend mode | `blur(4px)` | Inset gradient border via `::before` pseudo |

---

## Scrollbar

- `.no-scrollbar` utility hides scrollbars cross-browser (Webkit, Firefox, IE).
