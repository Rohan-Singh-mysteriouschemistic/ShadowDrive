"use client";
import { MagneticButton } from "./MagneticButton";
import { motion, useReducedMotion } from "framer-motion";
import { useNavigate } from "react-router-dom";

export default function DeploySection() {
  const reduce = useReducedMotion();
  const navigate = useNavigate();
  
  return (
    <section className="min-h-[100dvh] flex flex-col items-center justify-center text-center px-6 relative z-10">
      <motion.h2 
        initial={reduce ? false : { opacity: 0, y: 24 }}
        whileInView={{ opacity: 1, y: 0 }}
        viewport={{ once: true, amount: 0.3 }}
        transition={{ duration: 0.6, ease: [0.16, 1, 0.3, 1] }}
        className="text-[clamp(1.75rem,4vw,2.5rem)] font-bold text-[var(--ink)] mb-8" style={{ fontFamily: 'Space Grotesk, system-ui, sans-serif' }}
      >
        Ready to decentralize?
      </motion.h2>
      <motion.div
        initial={reduce ? false : { opacity: 0, y: 24 }}
        whileInView={{ opacity: 1, y: 0 }}
        viewport={{ once: true, amount: 0.3 }}
        transition={{ duration: 0.6, delay: 0.1, ease: [0.16, 1, 0.3, 1] }}
      >
        <MagneticButton size="lg" onClick={() => navigate('/auth?mode=deploy')}>Deploy a Node</MagneticButton>
      </motion.div>
    </section>
  );
}
