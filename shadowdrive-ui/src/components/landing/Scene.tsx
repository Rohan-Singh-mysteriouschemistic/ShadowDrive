"use client";
import { Canvas } from '@react-three/fiber';
import { Bloom, ChromaticAberration, EffectComposer, Vignette } from '@react-three/postprocessing';
import { useReducedMotion } from 'framer-motion';
import NetworkMesh from './NetworkMesh';
import React, { useEffect, useState } from 'react';

interface SceneProps {
  scrollProgress: React.MutableRefObject<number>;
  mousePosition: React.MutableRefObject<{x: number, y: number}>;
}

export default function Scene({ scrollProgress, mousePosition }: SceneProps) {
  const reduceMotion = useReducedMotion();
  const [mounted, setMounted] = useState(false);
  
  useEffect(() => {
    setMounted(true);
  }, []);

  const isReduced = reduceMotion || (typeof window !== 'undefined' && window.matchMedia('(prefers-reduced-motion: reduce)').matches);

  if (!mounted) return null;

  return (
    <div aria-hidden="true" className="fixed inset-0 z-0 pointer-events-none">
      <Canvas 
        dpr={[1, 1.5]} 
        camera={{ position: [0, 0, 30], fov: 60 }}
        frameloop={isReduced ? "never" : "always"}
      >
        <NetworkMesh scrollProgress={scrollProgress} mousePosition={mousePosition} />
        <EffectComposer>
          <Bloom intensity={0.4} luminanceThreshold={0.6} />
          <Vignette darkness={0.5} />
          <ChromaticAberration offset={[0.001, 0.001]} />
        </EffectComposer>
      </Canvas>
    </div>
  );
}
