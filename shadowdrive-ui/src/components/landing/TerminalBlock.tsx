"use client";
import { useRef } from "react";
import { gsap } from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";
import { useGSAP } from "@gsap/react";
import { useReducedMotion } from "framer-motion";

gsap.registerPlugin(useGSAP, ScrollTrigger);

export default function TerminalBlock() {
  const containerRef = useRef<HTMLDivElement>(null);
  const lineRefs = useRef<(HTMLDivElement | null)[]>([]);
  const reduceMotion = useReducedMotion();

  const lines = [
    { command: "INITIALIZING NODE CLUSTER...", status: "OK" },
    { command: "ESTABLISHING ENCRYPTED TUNNEL...", status: "OK" },
    { command: "REPLICATING CHUNK 0xfa3b...", status: "OK" },
    { command: "VERIFYING SHA-256 INTEGRITY...", status: "OK" },
    { command: "CLUSTER SYNCHRONIZED.", status: "LIVE" }
  ];

  useGSAP(() => {
    if (reduceMotion || !containerRef.current) return;
    
    lineRefs.current.forEach((ref, i) => {
      if (!ref) return;
      
      gsap.to(ref, {
        opacity: 1,
        duration: 0.4,
        scrollTrigger: {
          trigger: ref,
          start: "top 85%",
          toggleActions: "play none none none",
        },
        delay: i * 0.3,
      });
    });
  }, { scope: containerRef });

  return (
    <section className="min-h-[80vh] flex items-center justify-center px-6 relative z-10">
      <div ref={containerRef} className="w-full max-w-3xl bg-[var(--color-surface-container-lowest)] border border-[rgba(0,255,136,0.08)] rounded-lg p-8 font-mono text-[13px] shadow-2xl">
        <div className="flex gap-2 mb-6">
          <span className="w-3 h-3 rounded-full bg-white/10" />
          <span className="w-3 h-3 rounded-full bg-white/10" />
          <span className="w-3 h-3 rounded-full bg-white/10" />
        </div>
        {lines.map((line, i) => (
          <div 
            key={i} 
            ref={el => { lineRefs.current[i] = el; }} 
            className={`${reduceMotion ? 'opacity-100' : 'opacity-0'} mb-2`}
          >
            <span className="text-[var(--ink-muted)]">&gt; </span>
            <span className="text-[var(--ink)]">{line.command}</span>
            <span className={line.status === 'LIVE' ? 'text-[var(--accent)] ml-4 [text-shadow:0_0_8px_var(--accent-glow)]' : 'text-[var(--accent)]/60 ml-4'}>
              [{line.status}]
            </span>
          </div>
        ))}
      </div>
    </section>
  );
}
