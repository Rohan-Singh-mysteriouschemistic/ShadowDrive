"use client";
import { useRef } from "react";
import { gsap } from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";
import { useGSAP } from "@gsap/react";
import { useReducedMotion } from "framer-motion";

gsap.registerPlugin(useGSAP, ScrollTrigger);

export default function FeaturesPan() {
  const wrapRef = useRef<HTMLDivElement>(null);
  const trackRef = useRef<HTMLDivElement>(null);
  const reduceMotion = useReducedMotion();

  useGSAP(() => {
    if (reduceMotion || !wrapRef.current || !trackRef.current) return;
    
    // We have 3 panels. We'll scroll the track left by its scrollWidth minus one viewport.
    const distance = trackRef.current.scrollWidth - window.innerWidth;
    
    gsap.to(trackRef.current, {
      x: -distance,
      ease: "none",
      scrollTrigger: {
        trigger: wrapRef.current,
        start: "top top",
        end: () => `+=${distance * 1.5}`, // make it scroll a bit slower so users can read
        pin: true,
        scrub: 1, // lowered back to 1 for tighter response with lenis
        invalidateOnRefresh: true,
      },
    });
  }, { scope: wrapRef });

  return (
    <section ref={wrapRef} className="relative overflow-hidden bg-transparent">
      {/* We use a flex container for the horizontal track. 
          Using gap-0 and w-screen per panel, but we center the content 
          so the visual distance between text blocks isn't artificially huge. */}
      <div ref={trackRef} className="flex min-h-[100dvh] items-center">
        
        {/* Panel 1 */}
        <div className="w-screen h-full flex-shrink-0 flex items-center justify-center px-6 pt-20 md:pt-0">
          <div className="w-full max-w-2xl bg-surface-container-lowest/40 backdrop-blur-sm p-8 md:p-12 border border-white/5 rounded-2xl shadow-2xl">
            <h2 className="text-[clamp(1.75rem,3vw,2.5rem)] font-bold text-white leading-[1.15] tracking-[-0.02em] mb-4" style={{ fontFamily: 'Space Grotesk, system-ui, sans-serif' }}>
              Block-Level Deduplication
            </h2>
            <p className="text-[var(--ink-muted)] text-[1.1rem] leading-[1.6] mb-8">
              Every chunk is hashed. If it exists anywhere on the network, it’s not sent again.
              Massive bandwidth savings on redundant data.
            </p>
            <div className="font-mono text-[13px] text-[var(--accent)] flex items-center bg-black/40 p-4 rounded-md border border-[rgba(0,255,136,0.1)] w-fit">
              <span className="mr-2 text-white/40">&gt;</span> hash_check --strict<span className="w-2 h-4 bg-[var(--accent)] ml-1 animate-pulse" />
            </div>
          </div>
        </div>

        {/* Panel 2 */}
        <div className="w-screen h-full flex-shrink-0 flex items-center justify-center px-6 pt-20 md:pt-0">
          <div className="w-full max-w-2xl bg-surface-container-lowest/40 backdrop-blur-sm p-8 md:p-12 border border-white/5 rounded-2xl shadow-2xl">
            <h2 className="text-[clamp(1.75rem,3vw,2.5rem)] font-bold text-white leading-[1.15] tracking-[-0.02em] mb-4" style={{ fontFamily: 'Space Grotesk, system-ui, sans-serif' }}>
              Deterministic Conflict Resolution
            </h2>
            <p className="text-[var(--ink-muted)] text-[1.1rem] leading-[1.6] mb-8">
              Vector clocks guarantee consistent state across all nodes without a central arbiter.
              No more overwritten files.
            </p>
            <div className="font-mono text-[13px] text-[var(--accent)] flex items-center bg-black/40 p-4 rounded-md border border-[rgba(0,255,136,0.1)] w-fit">
              <span className="mr-2 text-white/40">&gt;</span> sync_resolve --vector-clock<span className="w-2 h-4 bg-[var(--accent)] ml-1 animate-pulse" />
            </div>
          </div>
        </div>

        {/* Panel 3 */}
        <div className="w-screen h-full flex-shrink-0 flex items-center justify-center px-6 pt-20 md:pt-0">
          <div className="w-full max-w-2xl bg-surface-container-lowest/40 backdrop-blur-sm p-8 md:p-12 border border-white/5 rounded-2xl shadow-2xl">
            <h2 className="text-[clamp(1.75rem,3vw,2.5rem)] font-bold text-white leading-[1.15] tracking-[-0.02em] mb-4" style={{ fontFamily: 'Space Grotesk, system-ui, sans-serif' }}>
              Chunk-Streamed Object Storage
            </h2>
            <p className="text-[var(--ink-muted)] text-[1.1rem] leading-[1.6] mb-8">
              Petabyte-scale files are sliced and streamed dynamically to bypass memory limits.
              Upload a 1TB file on a Raspberry Pi.
            </p>
            <div className="font-mono text-[13px] text-[var(--accent)] flex items-center bg-black/40 p-4 rounded-md border border-[rgba(0,255,136,0.1)] w-fit">
              <span className="mr-2 text-white/40">&gt;</span> stream_s3 --chunk=8M<span className="w-2 h-4 bg-[var(--accent)] ml-1 animate-pulse" />
            </div>
          </div>
        </div>

      </div>
    </section>
  );
}
