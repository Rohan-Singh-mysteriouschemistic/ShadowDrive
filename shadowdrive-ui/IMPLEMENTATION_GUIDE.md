# ShadowDrive Redesign — Implementation Guide

> This guide is the execution playbook for the DESIGN.md specification.
> It tells you **what to build, in what order, and exactly how.**

---

## Phase 0: Environment Setup

### 0.1 Install Dependencies

```bash
cd shadowdrive-ui
npm install @react-three/fiber @react-three/drei @react-three/postprocessing three gsap @gsap/react
npm install -D @types/three
```

### 0.2 Clean `index.html`

Remove the legacy CDN Three.js script tag:

```diff
- <!-- Three.js (used by LandingPage particle background) -->
- <script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"></script>
```

Three.js is now bundled via npm. The CDN tag conflicts with it.

### 0.3 Add TypeScript Declarations

Create `src/types/three.d.ts` if R3F types aren't resolving:

```ts
/// <reference types="@react-three/fiber" />
```

---

## Phase 1: The 3D Scene (Foundation)

Everything else sits on top of this. Build it first.

### 1.1 `src/components/landing/Scene.tsx`

The fixed-position R3F canvas that lives behind all HTML content.

**Key decisions:**
- `position: fixed; inset: 0; z-index: 0;` — sits behind everything.
- `<Canvas dpr={[1, 1.5]} camera={{ position: [0, 0, 30], fov: 60 }}>` — moderate FOV, not too wide.
- Post-processing via `@react-three/postprocessing`:
  - `<Bloom intensity={1.2} luminanceThreshold={0.3} />` — makes green nodes glow.
  - `<Vignette darkness={0.5} />` — darkens edges, draws eye to center.
  - `<ChromaticAberration offset={[0.001, 0.001]} />` — subtle prismatic edge.
- `aria-hidden="true"` on the wrapping div.

**Props:**
- `scrollProgress: React.MutableRefObject<number>` — a ref that goes from 0 to 1 as the page scrolls. Set by GSAP ScrollTrigger in the parent.
- `mousePosition: React.MutableRefObject<{x: number, y: number}>` — normalized mouse coords (-1 to 1). Set by a `pointermove` listener on `document`.

**Reduced motion:**
- Check `window.matchMedia('(prefers-reduced-motion: reduce)')`.
- If true: render one frame, then set `frameloop="never"`.
- If false: `frameloop="always"`.

### 1.2 `src/components/landing/NetworkMesh.tsx`

The 200-node (80 on mobile) interconnected mesh.

**Data structure:**
```ts
interface NodeData {
  id: number;
  position: THREE.Vector3;      // current position
  basePosition: THREE.Vector3;  // "home" position for spring return
  velocity: THREE.Vector3;
  color: THREE.Color;
}
```

**Initialization:**
- Distribute nodes randomly in a sphere of radius 15 using fibonacci sphere distribution (uniform).
- Each node is an `<Icosahedron args={[0.15, 1]}>` — geometric, not smooth.
- Material: `<meshBasicMaterial color="#10b981" transparent opacity={0.8} />` — basic material, no lighting needed since bloom handles the glow.

**Connections:**
- For each node, find all nodes within distance 4. Draw a `<Line>` between them.
- Line material: `color="#10b981"`, `opacity={0.15}`, `transparent`.
- Update connections every 30 frames (not every frame — expensive).

**`useFrame` loop:**
```
1. Read scrollProgress.current → determine morph target state.
2. For each node:
   a. Calculate target position based on scroll state:
      - 0.0-0.25: "spread" — nodes at basePosition * 1.5
      - 0.25-0.5: "cluster-1" — nodes 0-66 cluster left
      - 0.5-0.75: "cluster-2" — nodes 67-133 cluster center  
      - 0.75-0.9: "cluster-3" — nodes 134-200 cluster right
      - 0.9-1.0: "collapse" — all nodes lerp to (0,0,0)
   b. Apply mouse repulsion:
      - If distance(node, mouseWorldPos) < 5: push away from cursor.
   c. Spring physics: node.position.lerp(target, 0.03) — smooth, not instant.
3. Update connection lines.
```

**Critical performance rules:**
- Never allocate inside `useFrame`. Pre-allocate all `Vector3` instances in a `useMemo`.
- Use `instancedMesh` for the nodes (one draw call for 200 spheres, not 200).
- Connections can use a single `BufferGeometry` with `lineSegments`.

### 1.3 Mobile Detection

```ts
const isMobile = typeof window !== 'undefined' && window.innerWidth < 768;
const NODE_COUNT = isMobile ? 80 : 200;
```

Pass `NODE_COUNT` to `NetworkMesh`.

---

## Phase 2: HTML Sections (Over the Canvas)

All HTML sections sit in a `<main>` with `position: relative; z-index: 1;` so they scroll over the fixed canvas.

### 2.1 `src/components/landing/HeroSection.tsx`

**Layout:**
```
<section className="relative min-h-[100dvh] flex items-end pb-24 px-6 md:px-12 lg:px-16">
  <div className="max-w-3xl">
    <h1>SYNCHRONIZATION PERFECTED.</h1>
    <p>Decentralized file sync. Zero-trust encryption. Absolute consistency.</p>
    <MagneticButton>Deploy a Node</MagneticButton>
  </div>
</section>
```

- Text is bottom-left aligned (not centered — per DESIGN_VARIANCE=9, anti-center bias).
- H1 uses `clamp(3rem, 8vw, 5.5rem)`, weight 800, tracking `-0.03em`, `text-wrap: balance`.
- Subtext: ink-muted color, body-large size, max 12 words.
- One CTA only. No secondary.

**Animation (Framer Motion):**
- H1 words split into spans. Each span is a `motion.span` with:
  ```ts
  initial={{ opacity: 0, y: 40 }}
  animate={{ opacity: 1, y: 0 }}
  transition={{ duration: 0.7, delay: index * 0.06, ease: [0.16, 1, 0.3, 1] }}
  ```
- Subtext: same animation, delay starts after last word.
- CTA: spring entrance `type: "spring", stiffness: 100, damping: 20`, delay after subtext.

### 2.2 `src/components/landing/FeaturesPan.tsx`

**GSAP Horizontal Pan** — The most complex section.

**Structure:**
```tsx
<section ref={wrapRef} className="relative overflow-hidden">
  <div ref={trackRef} className="flex min-h-[100dvh] items-center">
    <Panel1 />  {/* w-screen flex-shrink-0 */}
    <Panel2 />
    <Panel3 />
  </div>
</section>
```

**GSAP Setup (inside `useGSAP`):**
```ts
import { useGSAP } from "@gsap/react";
import { gsap } from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";

gsap.registerPlugin(useGSAP, ScrollTrigger);

useGSAP(() => {
  if (reduceMotion) return;
  const distance = trackRef.current!.scrollWidth - window.innerWidth;
  gsap.to(trackRef.current, {
    x: -distance,
    ease: "none",
    scrollTrigger: {
      trigger: wrapRef.current,
      start: "top top",      // pin when section top hits viewport top
      end: () => `+=${distance}`,
      pin: true,
      scrub: 1,
      invalidateOnRefresh: true,
    },
  });
}, { scope: wrapRef });
```

**Each panel:**
- Full viewport width (`w-screen flex-shrink-0`).
- Panel 1: Split 60/40. Left = text block. Right = transparent (3D canvas shows through).
- Panel 2: Split 40/60 (inverted). Right = text block. Left = transparent.
- Panel 3: Centered text over transparent background.

**Text in each panel:**
- Headline: `clamp(1.75rem, 4vw, 2.5rem)`, weight 700.
- Description: 2 lines max, ink-muted.
- Terminal command: `font-mono text-[13px] text-accent/70`, with a blinking cursor span.

### 2.3 `src/components/landing/TerminalBlock.tsx`

A full-width section that looks like a terminal emulator.

**Visual:**
```
<section className="min-h-[80vh] flex items-center justify-center px-6">
  <div className="w-full max-w-3xl bg-[#111113] border border-white/5 rounded-lg p-8 font-mono text-[13px]">
    {/* Terminal chrome: 3 dots */}
    <div className="flex gap-2 mb-6">
      <span className="w-3 h-3 rounded-full bg-white/10" />
      <span className="w-3 h-3 rounded-full bg-white/10" />
      <span className="w-3 h-3 rounded-full bg-white/10" />
    </div>
    {/* Lines */}
    {lines.map((line, i) => (
      <div key={i} ref={lineRefs[i]} className="opacity-0 mb-2">
        <span className="text-ink-muted">&gt; </span>
        <span className="text-ink">{line.command}</span>
        <span className={line.status === 'LIVE' ? 'text-accent ml-4 glow' : 'text-accent/60 ml-4'}>
          [{line.status}]
        </span>
      </div>
    ))}
  </div>
</section>
```

**Animation (GSAP):**
```ts
useGSAP(() => {
  if (reduceMotion) return;
  lineRefs.forEach((ref, i) => {
    gsap.to(ref.current, {
      opacity: 1,
      duration: 0.4,
      scrollTrigger: {
        trigger: ref.current,
        start: "top 85%",
        toggleActions: "play none none none",
      },
      delay: i * 0.3,
    });
  });
}, { scope: containerRef });
```

The `[LIVE]` status gets a subtle glow:
```css
.glow { text-shadow: 0 0 8px oklch(72% 0.19 162 / 0.6); }
```

### 2.4 `src/components/landing/DeploySection.tsx`

**Layout:**
```
<section className="min-h-[100dvh] flex flex-col items-center justify-center text-center px-6">
  <h2 className="text-headline-lg mb-8 text-ink">Ready to decentralize?</h2>
  <MagneticButton size="lg">Deploy a Node</MagneticButton>
</section>
```

Maximum whitespace. The 3D sphere behind it does the talking.

### 2.5 `src/components/landing/Footer.tsx`

```
<footer className="border-t border-white/5 py-6 px-6 md:px-12 flex items-center justify-between text-ink-muted text-[13px] font-mono">
  <div className="flex items-center gap-2">
    <HexagonIcon className="w-4 h-4 text-accent" />
    <span>ShadowDrive</span>
  </div>
  <span>© 2026</span>
</footer>
```

No fat footer. No 4-column grid. One line.

---

## Phase 3: Reusable Components

### 3.1 `src/components/landing/MagneticButton.tsx`

A button that follows the cursor within a magnetic radius.

```tsx
import { motion, useMotionValue, useTransform, useReducedMotion } from "framer-motion";
import { useRef } from "react";

export function MagneticButton({ children, size = "md", ...props }) {
  const ref = useRef<HTMLButtonElement>(null);
  const reduce = useReducedMotion();
  const x = useMotionValue(0);
  const y = useMotionValue(0);

  function handleMouse(e: React.PointerEvent) {
    if (reduce) return;
    const rect = ref.current!.getBoundingClientRect();
    const centerX = rect.left + rect.width / 2;
    const centerY = rect.top + rect.height / 2;
    x.set((e.clientX - centerX) * 0.15);  // 15% of distance
    y.set((e.clientY - centerY) * 0.15);
  }

  function handleLeave() {
    x.set(0);
    y.set(0);
  }

  return (
    <motion.button
      ref={ref}
      style={{ x, y }}
      onPointerMove={handleMouse}
      onPointerLeave={handleLeave}
      whileTap={{ scale: 0.97 }}
      transition={{ type: "spring", stiffness: 200, damping: 20 }}
      className={`
        inline-flex items-center justify-center rounded-full
        bg-accent text-on-primary font-semibold
        cursor-pointer
        ${size === "lg" ? "px-8 py-4 text-lg" : "px-6 py-3 text-base"}
        hover:bg-accent-dim
        focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent
        active:scale-[0.97]
        transition-colors duration-150
      `}
      {...props}
    >
      {children}
    </motion.button>
  );
}
```

**Rules:**
- Uses `useMotionValue` for x/y — never `useState`.
- `whileTap` for tactile feedback.
- `focus-visible` for keyboard accessibility.
- Spring physics on position, CSS transition on color.

### 3.2 `src/components/landing/ShadowDriveLogo.tsx`

The brand "S" mark recreated as an inline SVG. The original `/Logo.jpeg` has a white background and **must not be used as an `<img>`** — it would look like a pasted sticker on the dark theme.

**Approach:**
- Trace the interlocking ribbon "S" shape from the JPEG as SVG `<path>` elements.
- Use two fills: `#10b981` (accent green) for the front facets, `#059669` (accent-dim) for the shadow/depth facets to preserve the 3D ribbon effect.
- The component accepts `size` (number, default 24) and `className` props.

```tsx
interface ShadowDriveLogoProps {
  size?: number;
  className?: string;
}

export function ShadowDriveLogo({ size = 24, className }: ShadowDriveLogoProps) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 100 120"
      fill="none"
      className={className}
      aria-hidden="true"
    >
      {/* Front facets - accent green */}
      <path d="M50 0 L85 20 L85 50 L50 70 L15 50 L15 20 Z" fill="#10b981" />
      {/* Shadow/depth facets - darker green */}
      <path d="M50 70 L85 50 L85 80 L50 100 Z" fill="#059669" />
      <path d="M50 70 L15 50 L15 80 L50 100 Z" fill="#047857" />
      {/* NOTE: The actual SVG paths must be traced from the original
           Logo.jpeg ribbon "S" shape. The paths above are placeholder
           geometry. The implementing agent should use the Logo.jpeg as
           reference to produce the correct interlocking "S" ribbon. */}
    </svg>
  );
}
```

**Usage (in nav/footer):**
```tsx
<div className="flex items-center gap-2">
  <ShadowDriveLogo size={24} />
  <span className="font-sans text-sm font-bold tracking-[0.08em] uppercase text-ink">
    Shadow Drive
  </span>
</div>
```

### 3.3 `src/components/landing/SplashScreen.tsx`

The 3D logo reveal video that plays once per session before the hero.

**Approach:**
- Reads/writes `sessionStorage` to only play on the first visit.
- Uses `mix-blend-mode: screen` so the video's light gray background disappears against the `#09090b` container, leaving only the glowing green logo.
- Sets `overflow: hidden` on the `<body>` while playing to lock scroll.

```tsx
import { useState, useEffect } from 'react';
import { useReducedMotion } from 'framer-motion';

export function SplashScreen({ onComplete }: { onComplete: () => void }) {
  const reduceMotion = useReducedMotion();
  const [isFading, setIsFading] = useState(false);
  const [isVisible, setIsVisible] = useState(() => {
    // Skip if reduced motion or if already visited this session
    if (reduceMotion || typeof window === 'undefined') return false;
    return !sessionStorage.getItem('sd-visited');
  });

  useEffect(() => {
    if (isVisible) {
      document.body.style.overflow = 'hidden';
    } else {
      document.body.style.overflow = '';
      onComplete();
    }
    return () => { document.body.style.overflow = ''; };
  }, [isVisible, onComplete]);

  if (!isVisible) return null;

  const finishSplash = () => {
    setIsFading(true);
    setTimeout(() => {
      sessionStorage.setItem('sd-visited', '1');
      setIsVisible(false);
    }, 600); // Matches CSS transition duration
  };

  return (
    <div 
      className={`fixed inset-0 z-50 bg-[#09090b] flex items-center justify-center transition-opacity duration-600 ease-out ${isFading ? 'opacity-0' : 'opacity-100'}`}
    >
      <video
        autoPlay
        muted
        playsInline
        src="/splash.mp4"
        onEnded={finishSplash}
        onError={finishSplash} // Fallback if video fails to load
        ref={(el) => { if (el) el.playbackRate = 1.5; }}
        className="w-full max-w-[400px] sm:max-w-[600px] object-contain mix-blend-screen"
      />
    </div>
  );
}
```

---

## Phase 4: Orchestration (`LandingPage.tsx`)

The new `LandingPage.tsx` is a thin orchestrator:

```tsx
import { useRef, useEffect, useState } from 'react';
import { gsap } from 'gsap';
import { ScrollTrigger } from 'gsap/ScrollTrigger';
import Scene from '../components/landing/Scene';
import HeroSection from '../components/landing/HeroSection';
import FeaturesPan from '../components/landing/FeaturesPan';
import TerminalBlock from '../components/landing/TerminalBlock';
import DeploySection from '../components/landing/DeploySection';
import Footer from '../components/landing/Footer';
import { SplashScreen } from '../components/landing/SplashScreen';

gsap.registerPlugin(ScrollTrigger);

export default function LandingPage() {
  const scrollProgress = useRef(0);
  const mousePosition = useRef({ x: 0, y: 0 });
  const mainRef = useRef<HTMLElement>(null);
  const [splashFinished, setSplashFinished] = useState(false);

  // Global scroll progress for 3D scene
  useEffect(() => {
    // Only init scroll trigger after splash finishes (if it exists) to avoid incorrect calculations
    if (!splashFinished) return;
    
    const trigger = ScrollTrigger.create({
      start: "top top",
      end: "bottom bottom",
      onUpdate: (self) => {
        scrollProgress.current = self.progress;
      },
    });

    const handlePointerMove = (e: PointerEvent) => {
      mousePosition.current = {
        x: (e.clientX / window.innerWidth) * 2 - 1,
        y: -(e.clientY / window.innerHeight) * 2 + 1,
      };
    };
    document.addEventListener('pointermove', handlePointerMove);

    return () => {
      trigger.kill();
      document.removeEventListener('pointermove', handlePointerMove);
    };
  }, [splashFinished]);

  return (
    <>
      <SplashScreen onComplete={() => setSplashFinished(true)} />
      <Scene scrollProgress={scrollProgress} mousePosition={mousePosition} />
      <main ref={mainRef} className="relative z-10">
        <HeroSection />
        <FeaturesPan scrollProgress={scrollProgress} />
        <TerminalBlock />
        <DeploySection />
        <Footer />
      </main>
    </>
  );
}
```

---

## Phase 5: CSS Cleanup

### 5.1 Remove Dead Classes from `index.css`

Remove (lines ~140-284 approximately — the landing-page-only utilities):
- `.emerald-text-glow` + `@keyframes shimmer`
- `.reveal-up` + `.reveal-up.is-visible`
- `.feature-card-reveal` + variants
- `.tilt-card` + variants
- `@keyframes float`
- `.topology-icon` + `@keyframes topology-pulse`
- `.liquid-glass` + `.liquid-glass::before`

### 5.2 Keep (Used by Dashboard / Auth)
- Lines 1-114 (`@import`, `@theme`, global resets)
- `.animate-pulse-emerald` + `@keyframes pulse-emerald`
- `.input-glow`
- `.glass-panel`, `.glass-panel-darker`
- `.page-header`
- `.pulse-dot` + `@keyframes pulse-dot`
- `.no-scrollbar`

---

## Phase 6: Verification

### 6.1 Build Check
```bash
cd shadowdrive-ui
npx tsc -b          # TypeScript compiles
npm run build       # Vite builds without errors
```

### 6.2 Visual Verification
```bash
npm run dev
```
Open `http://localhost:5173` and verify:
- [ ] 3D mesh renders on page load with bloom glow
- [ ] Mouse moves repel nearby nodes
- [ ] Scrolling morphs the mesh through all 5 states
- [ ] Hero text staggers in on load
- [ ] Features section pins and scrolls horizontally
- [ ] Terminal lines type in on scroll
- [ ] Deploy section sphere pulses
- [ ] Magnetic button follows cursor on hover
- [ ] Footer renders cleanly
- [ ] Mobile (375px): 80 nodes, no jank, horizontal pan still works
- [ ] `prefers-reduced-motion`: all motion disabled, static beautiful page
- [ ] Dashboard pages (`/vault`, `/nodes`, etc.) still work identically

### 6.3 Performance
- Lighthouse Performance score >= 85 on desktop
- 3D canvas maintains 60fps (check with Chrome DevTools Performance tab)
- No layout shift (CLS = 0)

### 6.4 Accessibility
- axe DevTools: 0 critical/serious violations
- Keyboard: Tab through hero CTA and deploy CTA, visible focus rings
- Screen reader: 3D canvas is `aria-hidden`, all text is accessible

---

## Execution Order Summary

| Order | Task | Dependencies |
|---|---|---|
| 1 | Install npm packages | None |
| 2 | Clean `index.html` (remove CDN script) | None |
| 3 | Build `Scene.tsx` + `NetworkMesh.tsx` | Packages installed |
| 4 | Build `MagneticButton.tsx` | None |
| 5 | Build `HeroSection.tsx` | MagneticButton |
| 6 | Build `FeaturesPan.tsx` | GSAP installed |
| 7 | Build `TerminalBlock.tsx` | GSAP installed |
| 8 | Build `DeploySection.tsx` | MagneticButton |
| 9 | Build `Footer.tsx` | None |
| 10 | Replace `LandingPage.tsx` | All sections built |
| 11 | Clean `index.css` | LandingPage replaced |
| 12 | Verify build + visual + a11y | All above |
