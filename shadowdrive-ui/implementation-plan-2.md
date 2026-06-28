# ShadowDrive Visual Overhaul — Implementation Plan 2

## Summary

Five major changes, applied globally across landing page, auth screens, and dashboard:

1. **Logo** → Hand-traced SVG of the ribbon "S" mark (no white bg, no text). Animated with pulse glow + floating particles everywhere it appears.
2. **Splash/Loading** → Ditch the video entirely. Build a pure CSS + Three.js loading animation using the logo mark for route transitions, initial load, and file uploads.
3. **Typography** → Replace Geist with **Space Grotesk** (headlines + body) paired with **JetBrains Mono** (code/labels). Space Grotesk has sharp geometric edges with a futuristic, coded feel — derived from Space Mono.
4. **3D Mesh** → Add continuous ambient drift + organic swarm behavior so particles are always alive, not just on scroll.
5. **Color Scheme** → "Midnight Emerald Matrix" — deep navy base (`#0a0e1a`) with electric emerald (`#00ff88`) accents.

---

## Detailed Changes

### 1. Logo Overhaul

#### [MODIFY] `src/components/landing/ShadowDriveLogo.tsx` → MOVE to `src/components/shared/ShadowDriveLogo.tsx`
- Hand-trace the ribbon "S" from the existing `public/logo.jpeg` as a clean SVG with two green tones (no white background, no "SHADOW DRIVE" text below)
- The original logo is a 3D ribbon "S" mark made of interlocking green facets — recreate this as SVG paths with gradient fills
- Add animated glow filter using SVG `<filter>` elements (`<feGaussianBlur>` + `<feComposite>` + `<feMerge>`) that pulses
- Add CSS keyframe animation for a breathing glow effect (`@keyframes logo-glow`)
- The component should accept `size`, `className`, and `animated` (boolean, default true) props
- When `animated=true`: the logo has a continuous subtle pulse glow and optionally tiny floating particles around it
- When `animated=false`: static logo with a soft static glow (for small sizes like sidebar)
- Must work at all sizes: 20px (footer), 24px (sidebar), 64px (auth), 120px+ (loading screen)

#### [MODIFY] `src/pages/AuthScreen.tsx`
- Replace `<img src="/logo.jpeg">` on line 157 (desktop branding) with `<ShadowDriveLogo size={64} />`
- Replace `<img src="/logo.jpeg">` on line 173 (mobile branding) with `<ShadowDriveLogo size={48} />`
- Update all hardcoded glow colors from `rgba(16,185,129,...)` to the new electric emerald `rgba(0,255,136,...)`
- Update the radial gradient on line 149 from `rgba(16,185,129,0.05)` to `rgba(0,255,136,0.05)`
- Update text shadow colors on lines 158, 174

#### [MODIFY] `src/layouts/DashboardLayout.tsx`
- Replace `<img src="/logo.jpeg">` on line 105 (mobile nav) with `<ShadowDriveLogo size={24} animated={false} />`
- Replace `<img src="/logo.jpeg">` on line 121 (desktop sidebar) with `<ShadowDriveLogo size={32} />`
- Update the text shadow on line 122 from `rgba(16, 185, 129, 0.3)` to `rgba(0, 255, 136, 0.3)`
- Update the pulse-dot keyframe colors in the inline `<style>` tag (lines 90-97) from `rgba(78, 222, 163, ...)` to `rgba(0, 255, 136, ...)`

#### [MODIFY] `src/components/landing/Footer.tsx`
- Update import path from `'./ShadowDriveLogo'` to `'../shared/ShadowDriveLogo'`

#### [MODIFY] `index.html`
- Change favicon from `<link rel="icon" type="image/jpeg" href="/logo.jpeg" />` to an inline SVG favicon or a generated `.svg` favicon file

---

### 2. Loading System (Replace Splash Video)

#### [DELETE] `src/components/landing/SplashScreen.tsx`
- Remove the entire video-based splash component

#### [NEW] `src/components/shared/LoadingScreen.tsx`
- Pure CSS + canvas loading animation featuring the animated logo mark
- Animation sequence:
  1. Black/navy screen with the ShadowDriveLogo centered
  2. Logo assembles from scattered particles (or fades in with a scale + glow burst)
  3. A radial pulse emanates outward from the logo
  4. The screen fades out to reveal the page content beneath
- Props: `onComplete: () => void`, `variant?: 'full' | 'mini'`
  - `full`: Used for initial page load (plays full animation ~2s)
  - `mini`: Used for route transitions (quick 0.5s fade with logo pulse)
- Uses `sessionStorage` flag (`sd-visited`) so the full animation only plays on first visit
- Respects `prefers-reduced-motion` — skips animation entirely
- The background color should match the new `#0a0e1a` navy
- Lock body scroll during animation

#### [MODIFY] `src/pages/LandingPage.tsx`
- Remove import of `SplashScreen` from `'../components/landing/SplashScreen'`
- Add import of `LoadingScreen` from `'../components/shared/LoadingScreen'`
- Replace `<SplashScreen onComplete={() => setSplashFinished(true)} />` with `<LoadingScreen onComplete={() => setSplashFinished(true)} />`

---

### 3. Typography — Space Grotesk

#### [MODIFY] `index.html`
- Replace the Geist Google Font import with Space Grotesk:
  - Old: `family=Geist:wght@400;600;700`
  - New: `family=Space+Grotesk:wght@400;500;600;700`
- Keep `family=JetBrains+Mono:wght@400;500` as-is

#### [MODIFY] `src/index.css`
- Update ALL `--font-family-*` tokens in the `@theme` block:
  - `--font-family-sans`: `"Space Grotesk", system-ui, sans-serif`
  - `--font-family-body-lg`: `"Space Grotesk", sans-serif`
  - `--font-family-body-md`: `"Space Grotesk", sans-serif`
  - `--font-family-display-lg`: `"Space Grotesk", sans-serif`
  - `--font-family-headline-md`: `"Space Grotesk", sans-serif`
  - `--font-family-headline-lg`: `"Space Grotesk", sans-serif`
  - `--font-family-headline-lg-mobile`: `"Space Grotesk", sans-serif`
- Keep `--font-family-mono`, `--font-family-label-md`, `--font-family-code-sm` as `"JetBrains Mono"`

#### [MODIFY] Landing page sections (inline font overrides)
- `src/components/landing/HeroSection.tsx`: Change all `style={{ fontFamily: 'Geist, ...' }}` to `'Space Grotesk, system-ui, sans-serif'`
- `src/components/landing/FeaturesPan.tsx`: Same font update in all inline styles
- `src/components/landing/Footer.tsx`: Same font update
- `src/components/landing/DeploySection.tsx`: Same font update if any inline font styles exist

---

### 4. Color Scheme — Midnight Emerald Matrix

#### [MODIFY] `src/index.css` — `@theme` block color tokens

Full token mapping (old → new):

```
--color-primary:                    #4edea3  →  #00ff88
--color-primary-fixed:              #6ffbbe  →  #66ffaa
--color-primary-fixed-dim:          #4edea3  →  #00ff88
--color-primary-container:          #10b981  →  #00cc6a
--color-on-primary:                 #003824  →  #002a1a
--color-on-primary-fixed:           #002113  →  #001a0e
--color-on-primary-fixed-variant:   #005236  →  #004428
--color-on-primary-container:       #00422b  →  #003820

--color-secondary:                  #68dba9  →  #4de8b0
--color-secondary-fixed:            #85f8c4  →  #80ffc0
--color-secondary-fixed-dim:        #68dba9  →  #4de8b0
--color-secondary-container:        #25a475  →  #1a9966
--color-on-secondary:               #003825  →  #002a1a
--color-on-secondary-fixed:         #002114  →  #001a0e
--color-on-secondary-fixed-variant: #005137  →  #004428
--color-on-secondary-container:     #00311f  →  #002816

--color-background:                 #131313  →  #0a0e1a
--color-on-background:              #e5e2e1  →  #e0e6ef
--color-surface:                    #131313  →  #0a0e1a
--color-surface-dim:                #131313  →  #0a0e1a
--color-surface-bright:             #3a3939  →  #2a3548
--color-surface-tint:               #4edea3  →  #00ff88
--color-surface-variant:            #353534  →  #1e2a3a
--color-surface-container-lowest:   #0e0e0e  →  #060912
--color-surface-container-low:      #1c1b1b  →  #0d1220
--color-surface-container:          #201f1f  →  #111827
--color-surface-container-high:     #2a2a2a  →  #1a2332
--color-surface-container-highest:  #353534  →  #243040
--color-on-surface:                 #e5e2e1  →  #e0e6ef
--color-on-surface-variant:         #bbcabf  →  #8899aa
--color-inverse-surface:            #e5e2e1  →  #e0e6ef
--color-inverse-on-surface:         #313030  →  #0a0e1a
--color-inverse-primary:            #006c49  →  #00994d
--color-outline:                    #86948a  →  #556677
--color-outline-variant:            #3c4a42  →  #1e3344
```

#### [MODIFY] `src/index.css` — utility class color updates
- `pulse-emerald` keyframe: `rgba(16, 185, 129, ...)` → `rgba(0, 255, 136, ...)`
- `input-glow`: `rgba(16, 185, 129, 0.3)` → `rgba(0, 255, 136, 0.3)`
- `glass-panel`: `rgba(17, 17, 17, 0.6)` → `rgba(10, 14, 26, 0.7)`
- `glass-panel-darker`: `rgba(17, 17, 17, 0.8)` → `rgba(10, 14, 26, 0.85)`
- `page-header`: `rgba(17, 17, 17, 0.6)` → `rgba(10, 14, 26, 0.7)`
- `pulse-dot` keyframe: `rgba(78, 222, 163, ...)` → `rgba(0, 255, 136, ...)`

#### [MODIFY] Landing page components — hardcoded color references
All of these files have hardcoded colors that need updating:

- `src/components/landing/HeroSection.tsx`:
  - CSS variable references like `var(--ink)`, `var(--ink-muted)`, `var(--accent)` etc. — these are custom vars not in the theme. Replace with Tailwind token equivalents (`text-on-surface`, `text-on-surface-variant`, `text-primary`, `bg-primary`)
  - Or define `--ink`, `--ink-muted`, `--accent`, `--accent-dim`, `--accent-glow` in index.css as aliases

- `src/components/landing/FeaturesPan.tsx`:
  - `#111113` → use `bg-surface-container-lowest` or the new navy equivalent
  - `oklch(30%_0_0_/_0.12)` → `rgba(0, 255, 136, 0.08)` for a subtle emerald border
  - `var(--ink)`, `var(--ink-muted)`, `var(--accent)` — same as above

- `src/components/landing/TerminalBlock.tsx`:
  - `#111113` → new navy surface
  - `oklch(30%_0_0_/_0.12)` → new border color
  - `var(--ink)`, `var(--ink-muted)`, `var(--accent)`, `var(--accent-glow)` — define or replace

- `src/components/landing/DeploySection.tsx`:
  - `var(--ink)` → `text-on-surface`

- `src/components/landing/Footer.tsx`:
  - `oklch(30%_0_0_/_0.12)` → new border color
  - `var(--ink)`, `var(--ink-muted)` → Tailwind tokens

- `src/components/landing/MagneticButton.tsx`:
  - `var(--accent)`, `var(--background)`, `var(--accent-dim)` — define these CSS vars or replace with Tailwind classes

#### [MODIFY] `src/components/landing/NetworkMesh.tsx`
- Node color: `#10b981` → `#00ff88`
- Line color: `#10b981` → `#00ff88`

#### [MODIFY] `src/components/landing/Scene.tsx`
- Increase bloom `intensity` from 1.2 to 1.5 to match the more electric color

#### [MODIFY] `src/pages/AuthScreen.tsx`
- All `rgba(16,185,129,...)` references → `rgba(0,255,136,...)`

#### Add CSS custom property aliases in `src/index.css` (after @theme block)
Define these as aliases so landing components don't need rewriting:
```css
:root {
  --ink: var(--color-on-surface);
  --ink-muted: var(--color-on-surface-variant);
  --accent: var(--color-primary);
  --accent-dim: var(--color-primary-container);
  --accent-glow: rgba(0, 255, 136, 0.4);
  --background: var(--color-background);
}
```

---

### 5. 3D Mesh — Always Alive

#### [MODIFY] `src/components/landing/NetworkMesh.tsx`

Major rework of the `useFrame` loop:

**Add ambient drift (always-on floating):**
- Each node gets a unique `driftSpeed` (0.2–0.8) and `driftOffset` (random 0–2π) assigned in `useMemo`
- In `useFrame`, add a time-based sinusoidal offset to each node's target position:
  ```
  driftX = Math.sin(time * node.driftSpeed + node.driftOffset) * 1.5
  driftY = Math.cos(time * node.driftSpeed * 0.7 + node.driftOffset + 1) * 1.0
  driftZ = Math.sin(time * node.driftSpeed * 0.5 + node.driftOffset + 2) * 1.0
  ```
- This ensures nodes are always moving, even when scroll is at 0

**Add organic swarm (boids-lite):**
- For each node, compute simple separation force (push away from nearby nodes within radius 3)
- Apply a weak alignment force (steer towards average velocity of neighbors)
- Weight: 50% ambient drift + scroll morphing, 50% swarm forces
- Keep mouse repulsion as-is

**Add gentle global rotation:**
- Use `useFrame((state) => { ... })` to access `state.clock.elapsedTime`
- Apply a very slow rotation to the entire group: `group.rotation.y = time * 0.05`
- Wrap the mesh + lines in a `<group>` ref

**Increase responsiveness:**
- Change lerp factor from `0.03` to `0.05`

**Performance guard:**
- Keep the "update lines every 3 frames" optimization
- The swarm neighbor check should use squared distances to avoid `Math.sqrt`

---

## Execution Order

1. `index.html` — fonts + favicon
2. `index.css` — color tokens + font tokens + CSS variable aliases
3. `src/components/shared/ShadowDriveLogo.tsx` — new animated logo
4. `src/components/shared/LoadingScreen.tsx` — new loading animation
5. `src/components/landing/NetworkMesh.tsx` — always-alive mesh
6. `src/components/landing/Scene.tsx` — bloom update
7. `src/components/landing/HeroSection.tsx` — fonts + colors
8. `src/components/landing/FeaturesPan.tsx` — fonts + colors
9. `src/components/landing/TerminalBlock.tsx` — colors
10. `src/components/landing/DeploySection.tsx` — fonts + colors
11. `src/components/landing/MagneticButton.tsx` — colors
12. `src/components/landing/Footer.tsx` — import path + fonts + colors
13. `src/pages/LandingPage.tsx` — swap SplashScreen → LoadingScreen
14. `src/pages/AuthScreen.tsx` — logo + colors
15. `src/layouts/DashboardLayout.tsx` — logo + colors
16. Delete `src/components/landing/SplashScreen.tsx`
17. Run `npx tsc -b && npm run build`
18. Run `npm run dev` and verify with browser

## Verification Plan

### Automated Tests
- `npx tsc -b` — TypeScript compilation must pass
- `npm run build` — Vite production build must succeed

### Manual Verification (Browser Subagent)
- Landing page: new colors (navy bg, electric green), Space Grotesk fonts, animated mesh always moving, loading animation on first visit
- Auth screen: new logo SVG (no JPEG, no white bg), updated glow colors
- Dashboard sidebar: new logo SVG, updated colors
- Route transition: loading animation plays briefly when navigating
