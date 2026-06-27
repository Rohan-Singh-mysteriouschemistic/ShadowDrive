---
status: draft
project: ShadowDrive
updated: 2026-06-27
register: brand
colors:
  background: "#09090b"
  surface: "#111113"
  surface-elevated: "#18181b"
  ink: "#fafafa"
  ink-muted: "#a1a1aa"
  accent: "#10b981"
  accent-dim: "#059669"
  accent-glow: "oklch(72% 0.19 162 / 0.4)"
  border: "oklch(30% 0 0 / 0.12)"
  error: "#ef4444"
typography:
  display: "Geist, system-ui, sans-serif"
  body: "Geist, system-ui, sans-serif"
  mono: "JetBrains Mono, monospace"
rounded:
  none: "0px"
  sm: "4px"
  md: "8px"
  lg: "12px"
  full: "9999px"
spacing:
  unit: "4px"
  scale: [4, 8, 12, 16, 24, 32, 48, 64, 96, 128]
---

# ShadowDrive — Website Redesign Specification

## Design Read

> Reading this as: **dark-tech P2P infrastructure product** for **developers and technical operators**, with a **terminal-native + high-fidelity 3D immersive** language, leaning toward **React Three Fiber + GSAP ScrollTrigger + Framer Motion on a Tailwind v4 + Vite foundation**.

### Dial Configuration

| Dial | Value | Reasoning |
|------|-------|-----------|
| **DESIGN_VARIANCE** | **9** | This is a brand showcase, not a dashboard. Asymmetric layouts, scroll-driven 3D storytelling, and unconventional section structures. |
| **MOTION_INTENSITY** | **9** | The user explicitly asked for "crazy animations, interactive elements." Every section earns its motion. |
| **VISUAL_DENSITY** | **3** | Minimalist color scheme + generous negative space. The 3D scene IS the visual density; the text breathes. |

---

## 1. Brand Identity

ShadowDrive is a decentralized, zero-trust, cryptographically secure P2P file synchronization engine. The website must feel like stepping inside a live node — not watching a marketing video about one.

**Scene sentence:** *A senior infrastructure engineer, alone at 2am in a dark office lit only by monitors, watches encrypted chunks replicate across a global mesh network in real-time. The interface is the machine itself.*

This sentence forces: deep dark mode, monospace accents, neon-on-black glow, terminal motifs earned by the product's actual nature (not aesthetic cosplay).

### What this is NOT
- Not a SaaS marketing page with cream backgrounds and trust badges
- Not glassmorphism cards floating over mesh gradients
- Not "three identical feature cards with icons"
- Not a particle background that serves no narrative purpose

### Signature Element
**The Decentralized Mesh** — A React Three Fiber scene of interconnected nodes that morphs in response to scroll position. Each section of the page triggers a different state in the 3D scene, creating a continuous visual narrative where the 3D IS the storytelling device.

### Logo Handling

The brand logo is a 3D ribbon-style interlocking "S" mark (see `/Logo.jpeg`). **The JPEG must NOT be used directly** — it has a white background baked in and will look like a pasted sticker on the dark theme.

**Required approach:**
1. **Recreate the "S" mark as an inline SVG React component** (`ShadowDriveLogo.tsx`) that traces the ribbon/möbius "S" shape from the original.
2. The SVG uses `currentColor` or the `--accent` green (`#10b981`) as its fill, with darker shading (`#059669`) for the 3D ribbon depth/shadow facets.
3. On the dark background, the green SVG glows natively — no background-removal hacks, no `mix-blend-mode` tricks.
4. The SVG component accepts `size` and `className` props for reuse across the nav, hero, footer, and favicon.
5. The wordmark "SHADOW DRIVE" text next to the icon is rendered as actual `<span>` text in Geist font (weight 700, tracking `0.08em`, uppercase) — not part of the SVG.

**Where it appears:**
- **Hero nav** (top-left): Icon (24px) + wordmark
- **Footer** (bottom-left): Icon (20px) + wordmark
- **Favicon**: The existing `/logo.jpeg` is fine for the browser tab — favicons are tiny and background color doesn't matter.

---

## 2. Color System

Cold, sharp, digital. No warm tints. One saturated accent used with surgical precision.

| Token | Value | Usage |
|---|---|---|
| `--background` | `#09090b` | Page body. True OLED black. |
| `--surface` | `#111113` | Slightly elevated panels. |
| `--surface-elevated` | `#18181b` | Cards, modals, tooltips. |
| `--ink` | `#fafafa` | Primary text. Contrast >= 15:1 on background. |
| `--ink-muted` | `#a1a1aa` | Secondary text. Contrast >= 5.4:1 on background. |
| `--accent` | `#10b981` | The electric green. Active states, 3D node glow, CTA fills, terminal cursor. |
| `--accent-dim` | `#059669` | Hover state for accent, secondary accent uses. |
| `--accent-glow` | `oklch(72% 0.19 162 / 0.4)` | Box-shadow / text-shadow glow halo. |
| `--border` | `oklch(30% 0 0 / 0.12)` | Subtle dividers. Near-invisible until needed. |
| `--error` | `#ef4444` | Destructive actions only. |

**Color rules:**
- Accent appears on <= 15% of the page surface. It's a scalpel, not a paintbrush.
- No gradients on text (`background-clip: text` is banned per impeccable guidelines).
- No warm grays. The gray ramp stays in the zinc family (cool-neutral).

---

## 3. Typography

| Role | Family | Size | Weight | Tracking | Line Height |
|---|---|---|---|---|---|
| **Display** (hero H1) | Geist | `clamp(3rem, 8vw, 5.5rem)` | 800 | `-0.03em` | `1.05` |
| **Headline** (section H2) | Geist | `clamp(1.75rem, 4vw, 2.5rem)` | 700 | `-0.02em` | `1.15` |
| **Body** | Geist | `1rem` (16px) | 400 | `0` | `1.6` |
| **Body Large** | Geist | `1.125rem` (18px) | 400 | `0` | `1.6` |
| **Mono / Terminal** | JetBrains Mono | `0.8125rem` (13px) | 400 | `0.02em` | `1.5` |
| **Label** | JetBrains Mono | `0.6875rem` (11px) | 500 | `0.08em` | `1.4` |

**Typography rules:**
- `text-wrap: balance` on all headings.
- `text-wrap: pretty` on body paragraphs.
- Body text capped at `max-w-[65ch]`.
- Display letter-spacing floor: `>= -0.04em` (per impeccable). We use `-0.03em`.
- Hero capped at `5.5rem` (~88px). No shouting.
- No serif fonts anywhere. Geist carries the personality.

---

## 4. The 3D Architecture (React Three Fiber)

### Technology Stack

| Package | Purpose |
|---|---|
| `@react-three/fiber` | Declarative Three.js in React |
| `@react-three/drei` | Helpers (Float, MeshDistortMaterial, Environment, Stars, etc.) |
| `@react-three/postprocessing` | Bloom, chromatic aberration, vignette |
| `three` | Core 3D engine |

### The Scene: "Living Network Mesh"

A persistent R3F `<Canvas>` spans the full viewport behind the page content. It renders a network of ~200 interconnected glowing nodes (icosahedrons, not spheres — geometric, not organic).

#### Node Behavior
- **Idle state**: Nodes drift slowly in 3D space with subtle spring physics. Connections between nearby nodes pulse with faint green light.
- **Mouse interaction**: Nodes within a radius of the cursor gently repel outward (magnetic repulsion via `useFrame` + distance calculation). This is computed in `useMotionValue` space — never `useState`.
- **Scroll-driven morphing** (via GSAP ScrollTrigger):
  - **Hero section** (0-100vh): Full swarm, spread wide. Bloom is at maximum.
  - **Features section** (100-300vh): Nodes cluster into 3 distinct groups, representing the 3 core features (Deduplication, Conflict Resolution, Object Storage). As each feature scrolls into view, its cluster brightens.
  - **Footer section**: Nodes collapse into a single dense sphere — the "unified truth" — then fade to a single pulsing dot.

#### Post-Processing Pipeline

Scene -> Bloom (intensity: 1.2, luminanceThreshold: 0.3) -> ChromaticAberration (offset: [0.001, 0.001]) -> Vignette (darkness: 0.5)

#### Performance Constraints
- `dpr={[1, 1.5]}` — cap pixel ratio.
- Node count: 200 on desktop, 80 on mobile (detected via `window.innerWidth < 768`).
- `frameloop="demand"` when the canvas is not in viewport (IntersectionObserver).
- Bloom resolution halved on mobile.

#### Reduced Motion Fallback
When `prefers-reduced-motion: reduce`:
- Canvas renders a single static frame (no animation loop).
- Nodes are positioned in their "hero" arrangement.
- Bloom stays active (it's a visual treatment, not motion).
- No mouse interaction, no scroll morphing.

---

## 5. Page Architecture & Scroll Narrative

The page is a single, continuous scroll-driven story. No section looks like any other. Each earns its layout.

### Section Map

| # | Section | Layout | 3D State | Motion |
|---|---|---|---|---|
| 0 | **Splash (first visit only)** | Full-viewport centered video. `#09090b` background. | Canvas hidden. | Logo reveal video plays at 1.5x speed, then cross-fades out. |
| 1 | **Hero** | Full-bleed. Left-aligned text over R3F canvas. | Full swarm, wide spread | GSAP stagger reveal on headline words. Spring entrance on CTA. |
| 2 | **Features (Scroll-Pinned)** | GSAP horizontal pan. 3 panels slide horizontally as user scrolls vertically. | Nodes cluster into 3 groups, each lighting up per panel. | Horizontal scroll-hijack via GSAP ScrollTrigger `pin: true`. |
| 3 | **Architecture** | Full-width terminal block. Monospace text typing out a real sync sequence. | Nodes form a ring topology. | Typewriter effect on terminal lines. Cursor blink. |
| 4 | **CTA / Deploy** | Centered. Single massive headline + single button. Maximum negative space. | Nodes collapse into a single dense pulsing sphere. | Button has magnetic hover (useMotionValue). Sphere pulses. |
| 5 | **Footer** | Minimal. Left: logo + copyright. Right: single nav link. No clutter. | Single dot. | Fade in. |

### Section Detail

#### 5.0 Splash Screen (Logo Reveal)

The 3D logo reveal video (`/public/splash.mp4`) plays as a cinematic intro before the user sees the hero. This creates a "brand moment" — like a game studio logo before the title screen.

**Behavior:**
- **First visit only.** Stored in `sessionStorage('sd-visited')`. On repeat visits, the splash is skipped entirely and the hero loads immediately.
- **Video**: Plays at **1.5x speed** (~6.7 seconds instead of 10). `autoPlay`, `muted`, `playsInline`. No controls visible.
- **Color treatment**: The original video has a light gray background. Apply `mix-blend-mode: screen` on the `<video>` element inside a `bg-[#09090b]` container. This makes the gray background disappear and only the green logo shows — no hacky inversion, no re-encoding needed.
- **Exit transition**: When the video's `onEnded` fires, the splash container fades out over 600ms (`opacity: 0`, `transition: opacity 600ms ease-out`), then is removed from the DOM.
- **Scroll lock**: While the splash is visible, `overflow: hidden` on `<body>` to prevent scrolling.
- **`prefers-reduced-motion`**: Skip the splash entirely. Go straight to hero.
- **Mobile**: Same behavior, but the video is capped at `max-w-[280px]` to avoid dominating small screens.

**What NOT to do:**
- Don't use Remotion (the video already exists — re-coding it in React is wasted effort).
- Don't loop it. It plays once and dies.
- Don't add a "skip" button. At 1.5x speed it's under 7 seconds — skip buttons signal "we know this is annoying."

#### 5.1 Hero
- **Headline**: `SYNCHRONIZATION PERFECTED.` — Revealed word-by-word via GSAP SplitText-style stagger (each word fades up with a 60ms delay).
- **Subtext**: `Decentralized file sync. Zero-trust encryption. Absolute consistency.` — Max 12 words. Appears 400ms after headline completes.
- **CTA**: `Deploy a Node` — Single primary button. Pill-shaped (`rounded-full`). Electric green fill. On hover: magnetic pull effect (button follows cursor within a 20px radius using `useMotionValue`/`useTransform`). On press: `scale(0.97)` tactile push.
- **No eyebrow. No trust logos. No secondary CTA.** This hero is a statement, not a pitch deck.

#### 5.2 Features (Horizontal Pan)
Three full-viewport panels that scroll horizontally as the user scrolls vertically. Each panel:

**Panel 1: Deduplication**
- Left 60%: Large headline `Block-Level Deduplication` + 2-line description + terminal command `> hash_check --strict`.
- Right 40%: The 3D scene (shared canvas) shows identical nodes merging together.

**Panel 2: Conflict Resolution**
- Layout mirrors but inverted (text right, 3D interaction left).
- Headline: `Deterministic Conflict Resolution`
- Terminal: `> sync_resolve --vector-clock`
- 3D: Colliding nodes bounce off each other with spring physics.

**Panel 3: Object Storage**
- Full-width panel. Text centered over a zoomed-in view of data chunks streaming between nodes.
- Headline: `Chunk-Streamed Object Storage`
- Terminal: `> stream_s3 --chunk=8M`

#### 5.3 Architecture
A full-width dark panel styled like a live terminal session. Monospace text types out line by line:

```
> INITIALIZING NODE CLUSTER...        [OK]
> ESTABLISHING ENCRYPTED TUNNEL...    [OK]
> REPLICATING CHUNK 0xfa3b...         [OK]
> VERIFYING SHA-256 INTEGRITY...      [OK]
> CLUSTER SYNCHRONIZED.               [LIVE]
```

Each line appears with a typewriter effect (GSAP `staggerFrom` on characters). The `[OK]` / `[LIVE]` badges glow green with the accent-glow shadow. The 3D scene behind shows nodes forming a ring topology.

#### 5.4 CTA / Deploy
Maximum negative space. The entire viewport is dark with a single centered block:

Headline: `Ready to decentralize?`
Button: `Deploy a Node`

The 3D swarm has collapsed into a single, dense, pulsing sphere directly behind the text. The sphere breathes (scale oscillates 1.0 to 1.05 with a 3s spring cycle).

#### 5.5 Footer
Minimal. No fat footer with 4 columns of links.
- Left: Logo icon + `ShadowDrive` wordmark.
- Right: `(c) 2026`
- Single line. Border-top `1px solid var(--border)`.

---

## 6. Motion Design (GSAP + Framer Motion)

### GSAP (scroll-driven, pinned, hijacked)
- **Horizontal Pan** (Section 2): GSAP ScrollTrigger `pin: true`, `scrub: 1`. See canonical skeleton in design-taste-frontend Section 5.B.
- **Typewriter** (Section 3): `gsap.from(chars, { opacity: 0, stagger: 0.02 })`.
- **3D Scroll Sync**: GSAP ScrollTrigger `scrub: true` drives a progress value (0 to 1) that the R3F scene reads via a shared ref. No React state re-renders.

### Framer Motion (UI element animation)
- **Hero text reveal**: `motion.div` with `initial={{ opacity: 0, y: 24 }}`, `animate={{ opacity: 1, y: 0 }}`, staggered via `transition.delay`.
- **Button magnetic hover**: `useMotionValue` for `x` and `y`, `useTransform` to map cursor offset to button translation. Never `useState`.
- **Section reveals**: `whileInView` with `viewport={{ once: true, amount: 0.3 }}` for sections that aren't GSAP-controlled.

### Motion Rules
- **Every animation must be motivated.** What does it communicate? If the answer is "it looked cool," cut it.
- **`prefers-reduced-motion`**: All GSAP timelines check `useReducedMotion()` before creating. Framer Motion uses `initial={reduce ? false : ...}`.
- **No `window.addEventListener("scroll")`**. Ever. Use GSAP ScrollTrigger or Framer Motion `useScroll`.
- **No `useState` for continuous values.** Mouse position, scroll progress, spring physics — all via `useMotionValue`.
- **Easing**: Exponential ease-out (`[0.16, 1, 0.3, 1]`) for reveals. Spring (`stiffness: 100, damping: 20`) for interactive elements. No bounce. No elastic.

---

## 7. Component Architecture

```
shadowdrive-ui/src/
  pages/
    LandingPage.tsx          -- Orchestrator. Composes all sections.
  components/
    landing/
      Scene.tsx              -- R3F Canvas, camera, post-processing
      NetworkMesh.tsx         -- The 200-node swarm. useFrame loop.
      HeroSection.tsx         -- Text overlay. Framer Motion reveals.
      FeaturesPan.tsx         -- GSAP horizontal pan with 3 panels.
      TerminalBlock.tsx       -- Typewriter terminal section.
      DeploySection.tsx       -- Final CTA with pulsing sphere.
      Footer.tsx              -- Minimal footer.
      MagneticButton.tsx      -- Reusable magnetic hover button.
```

### Key Implementation Notes
- `Scene.tsx` renders a single `<Canvas>` that is `position: fixed` behind all content. The HTML sections scroll over it.
- `NetworkMesh.tsx` reads a `scrollProgress` ref (set by GSAP ScrollTrigger in `LandingPage.tsx`) and morphs node positions accordingly. This avoids React re-renders entirely.
- All `landing/` components are client-side only (this is a Vite SPA, no RSC concerns).

---

## 8. Dependencies to Add

```bash
npm install @react-three/fiber @react-three/drei @react-three/postprocessing three gsap @gsap/react
```

**Already installed:**
- `framer-motion` (v12.40.0)
- `tailwindcss` (v4.3.0)
- `react` (v19.2.6)

**To remove from `index.html`:**
- The CDN `<script>` tag for `three.js r128` (we'll use the npm package instead).

---

## 9. Accessibility & Performance

### Accessibility
- All text meets WCAG AA contrast (>= 4.5:1 body, >= 3:1 large text). Verified above in color table.
- `prefers-reduced-motion` fully respected (static fallback for all animation).
- Keyboard focus visible on all interactive elements (`outline: 2px solid var(--accent)`).
- The 3D canvas has `aria-hidden="true"` — it's decorative, not informational.
- Semantic HTML: `<header>`, `<main>`, `<section>`, `<footer>`.

### Performance
- R3F canvas: `dpr={[1, 1.5]}`, 200 nodes desktop / 80 mobile, `frameloop="demand"` when off-screen.
- GSAP animations: hardware-accelerated (`transform` + `opacity` only).
- Code-split: `LandingPage.tsx` is already lazy-loaded in `App.tsx`.
- Fonts: Currently loaded via Google Fonts CDN link — acceptable for now, but should migrate to `@font-face` self-hosting for production.
- Bundle: R3F + Three.js adds ~150KB gzipped. This is the cost of the 3D experience and is acceptable for a landing page that IS the brand.

---

## 10. CSS Changes Required

### Clean up `index.css`
The following classes should be **removed** (they're artifacts of the old landing page and are now replaced by GSAP/Framer Motion):
- `.reveal-up`, `.reveal-up.is-visible`
- `.feature-card-reveal`, `.feature-card-reveal.is-active`, `.feature-card-reveal:hover`
- `.tilt-card`, `.tilt-card:hover`
- `@keyframes float`
- `.topology-icon`, `@keyframes topology-pulse`
- `.liquid-glass`, `.liquid-glass::before`
- `.emerald-text-glow`, `@keyframes shimmer`

### Keep
- `.glass-panel`, `.glass-panel-darker` (used by dashboard pages)
- `.page-header` (used by dashboard pages)
- `.pulse-dot`, `@keyframes pulse-dot` (used by dashboard pages)
- `.animate-pulse-emerald`, `@keyframes pulse-emerald` (used by dashboard pages)
- `.input-glow` (used by AuthScreen)
- `.no-scrollbar` (used globally)
- All `@theme` tokens (they serve the whole app)

### Add
New utility classes for the landing page will live in the component files themselves (Tailwind utilities) or as scoped CSS modules if needed. No new global CSS.

---

## 11. What Stays the Same

**Critical constraint from the user: "the functioning of the code should remain the same."**

- **All dashboard pages** (`/vault`, `/conflicts`, `/nodes`, `/health`, `/network`, `/transfers`) are untouched.
- **AuthScreen** is untouched.
- **DashboardLayout** is untouched.
- **`App.tsx` routing** is untouched.
- **`api.ts`, `queryClient.ts`, `useEventStream.ts`** are untouched.
- **`index.css` @theme tokens** are preserved (they power the dashboard).
- The **only file being replaced** is `LandingPage.tsx`, and new component files are added under `components/landing/`.
