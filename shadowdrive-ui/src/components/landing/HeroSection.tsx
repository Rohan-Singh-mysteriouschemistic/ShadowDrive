"use client";
import { useRef } from "react";
import { motion, useReducedMotion } from "framer-motion";
import { gsap } from "gsap";
import { useGSAP } from "@gsap/react";

gsap.registerPlugin(useGSAP);

export default function HeroSection() {
  const reduce = useReducedMotion();
  const titleRef = useRef<HTMLHeadingElement>(null);
  
  useGSAP(() => {
    if (reduce || !titleRef.current) return;
    
    // Clean slide up fade-in
    const chars = titleRef.current.querySelectorAll('.char');
    gsap.fromTo(chars, 
      { opacity: 0, y: 40 },
      { 
        opacity: 1, 
        y: 0,
        duration: 0.8, 
        stagger: 0.02,
        ease: "power3.out",
        delay: 0.2
      }
    );
  }, { scope: titleRef });

  const line1 = "SYNCHRONIZATION";
  const line2 = "PERFECTED.";
  const chars1 = line1.split("");
  // Adding space manually so they can sit on the same line if needed, 
  // but we are stacking them as blocks.
  const chars2 = line2.split("");
  
  return (
    <section className="relative min-h-[100dvh] flex items-end pb-24 px-6 md:px-12 lg:px-16 overflow-hidden">
      
      <div className="max-w-4xl relative z-10">
        <h1 ref={titleRef} className="mb-8 select-none" style={{ textWrap: 'balance', fontFamily: 'Space Grotesk, system-ui, sans-serif' }}>
          
          {/* Line 1 */}
          <span className="block text-[clamp(2.5rem,5vw,4.5rem)] font-bold tracking-tight leading-[1.1] text-white">
            {chars1.map((char, i) => (
              <span key={`l1-${i}`} className="char inline-block">{char === " " ? "\u00A0" : char}</span>
            ))}
          </span>
          
          {/* Line 2 */}
          <span className="block text-[clamp(2.5rem,5vw,4.5rem)] font-bold tracking-tight leading-[1.0] mt-1 text-[var(--accent)]">
            {chars2.map((char, i) => (
              <span key={`l2-${i}`} className="char inline-block">{char === " " ? "\u00A0" : char}</span>
            ))}
          </span>
        </h1>

        {/* Animated underline bar */}
        <motion.div
          initial={reduce ? false : { scaleX: 0, opacity: 0 }}
          animate={{ scaleX: 1, opacity: 1 }}
          transition={{ duration: 1.5, delay: 1.5, ease: "circOut" }}
          className="h-[2px] w-48 mb-10 origin-left"
          style={{ background: 'linear-gradient(90deg, var(--accent), transparent)' }}
        />

        <motion.p
          initial={reduce ? false : { opacity: 0, x: -30 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ duration: 1, delay: 1.8, ease: "easeOut" }}
          className="text-[1.125rem] md:text-[1.25rem] font-medium text-white/70 max-w-[50ch] tracking-wide" style={{ textWrap: 'pretty', lineHeight: '1.7', fontFamily: 'Space Grotesk, sans-serif' }}
        >
          Decentralized file sync. Zero-trust encryption. Absolute consistency.
        </motion.p>
        
        {/* MagneticButton removed as requested */}
      </div>
    </section>
  );
}
