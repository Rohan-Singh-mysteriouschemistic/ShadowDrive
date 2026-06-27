"use client";
import { motion, useMotionValue, useReducedMotion } from "framer-motion";
import { useRef } from "react";
import type { HTMLMotionProps } from "framer-motion";

interface MagneticButtonProps extends HTMLMotionProps<"button"> {
  size?: "md" | "lg";
}

export function MagneticButton({ children, size = "md", ...props }: MagneticButtonProps) {
  const ref = useRef<HTMLButtonElement>(null);
  const reduce = useReducedMotion();
  const x = useMotionValue(0);
  const y = useMotionValue(0);

  function handleMouse(e: React.PointerEvent) {
    if (reduce) return;
    const rect = ref.current!.getBoundingClientRect();
    const centerX = rect.left + rect.width / 2;
    const centerY = rect.top + rect.height / 2;
    x.set((e.clientX - centerX) * 0.15);
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
        inline-flex items-center justify-center rounded-[9999px]
        bg-[var(--accent)] text-[var(--background)] font-semibold
        cursor-pointer
        ${size === "lg" ? "px-8 py-4 text-lg" : "px-6 py-3 text-base"}
        hover:bg-[var(--accent-dim)]
        focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--accent)]
        active:scale-[0.97]
        transition-colors duration-150
      `}
      {...props}
    >
      {children}
    </motion.button>
  );
}
