"use client";
import { useState, useEffect, useCallback } from 'react';
import { useReducedMotion } from 'framer-motion';
import { ShadowDriveLogo } from './ShadowDriveLogo';

export function LoadingScreen({ onComplete, variant = 'full' }: { onComplete: () => void, variant?: 'full' | 'mini' }) {
  const reduceMotion = useReducedMotion();
  const [phase, setPhase] = useState<'initial' | 'assembling' | 'pulsing' | 'fading' | 'done'>('initial');
  const [isVisible, setIsVisible] = useState(false);

  const stableOnComplete = useCallback(onComplete, []);

  useEffect(() => {
    if (reduceMotion) {
      stableOnComplete();
      return;
    }

    // Determine timing: first visit gets the full ceremony, subsequent reloads get a quick pulse
    const visited = sessionStorage.getItem('sd-visited');
    const isFirstVisit = !visited;

    // Always show the loading screen
    setIsVisible(true);

    if (variant === 'full' && isFirstVisit) {
      // Full animation (~2.4s) on first visit
      setTimeout(() => setPhase('assembling'), 100);
      setTimeout(() => setPhase('pulsing'), 1000);
      setTimeout(() => setPhase('fading'), 1800);
      setTimeout(() => {
        sessionStorage.setItem('sd-visited', '1');
        setIsVisible(false);
        setPhase('done');
        stableOnComplete();
      }, 2400);
    } else {
      // Quick pulse (~0.9s) on subsequent reloads
      setPhase('assembling');
      setTimeout(() => setPhase('pulsing'), 200);
      setTimeout(() => setPhase('fading'), 600);
      setTimeout(() => {
        setIsVisible(false);
        setPhase('done');
        stableOnComplete();
      }, 900);
    }
  }, [reduceMotion, stableOnComplete, variant]);

  useEffect(() => {
    if (isVisible) {
      document.body.style.overflow = 'hidden';
    } else {
      document.body.style.overflow = '';
    }
    return () => { document.body.style.overflow = ''; };
  }, [isVisible]);

  if (!isVisible) return null;

  return (
    <div 
      className={`fixed inset-0 z-[100] bg-background flex items-center justify-center transition-opacity duration-500 ease-in-out ${phase === 'fading' ? 'opacity-0 pointer-events-none' : 'opacity-100'}`}
    >
      <div className="relative flex items-center justify-center">
        {/* The pulse ring */}
        <div 
          className={`absolute inset-0 rounded-full border border-primary transition-all duration-700 ease-out ${
            phase === 'pulsing' || phase === 'fading' ? 'scale-[3] opacity-0' : 'scale-0 opacity-100'
          }`}
        />
        
        {/* The Logo */}
        <div className={`transition-all duration-700 ease-out ${
          phase === 'initial' ? 'opacity-0 scale-50' : 
          phase === 'assembling' ? 'opacity-100 scale-100' :
          phase === 'pulsing' ? 'opacity-100 scale-110' :
          'opacity-100 scale-100'
        }`}>
          <ShadowDriveLogo size={120} animated={true} />
        </div>
      </div>
    </div>
  );
}
