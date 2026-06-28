"use client";
import { useRef, useEffect, useState } from 'react';
import { gsap } from 'gsap';
import { ScrollTrigger } from 'gsap/ScrollTrigger';
import Lenis from 'lenis';
import Scene from '../components/landing/Scene';
import HeroSection from '../components/landing/HeroSection';
import FeaturesPan from '../components/landing/FeaturesPan';
import TerminalBlock from '../components/landing/TerminalBlock';
import DeploySection from '../components/landing/DeploySection';
import Footer from '../components/landing/Footer';
import { LoadingScreen } from '../components/shared/LoadingScreen';
import LandingNav from '../components/landing/LandingNav';

gsap.registerPlugin(ScrollTrigger);

export default function LandingPage() {
  const scrollProgress = useRef(0);
  const mousePosition = useRef({ x: 0, y: 0 });
  const mainRef = useRef<HTMLElement>(null);
  const [splashFinished, setSplashFinished] = useState(false);

  // Global scroll progress for 3D scene
  useEffect(() => {
    // Wait for the loading screen to finish before setting up scroll/pointer tracking
    if (!splashFinished) {
      return;
    }

    // Initialize smooth scrolling
    const lenis = new Lenis({
      lerp: 0.06,
      duration: 1.2,
      smoothWheel: true,
    });

    // Sync Lenis with GSAP ScrollTrigger
    lenis.on('scroll', ScrollTrigger.update);
    
    // Use GSAP's ticker to run Lenis so they are perfectly in sync
    gsap.ticker.add((time) => {
      lenis.raf(time * 1000);
    });
    // Prevent GSAP from throttling when scrolling rapidly
    gsap.ticker.lagSmoothing(0);
    
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
      gsap.ticker.remove(lenis.raf);
      lenis.destroy();
    };
  }, [splashFinished]);

  return (
    <>
      <LoadingScreen onComplete={() => setSplashFinished(true)} />
      <LandingNav />
      <Scene scrollProgress={scrollProgress} mousePosition={mousePosition} />
      <main ref={mainRef} className="relative z-10 bg-transparent">
        <div id="hero">
          <HeroSection />
        </div>
        <div id="features">
          <FeaturesPan />
        </div>
        <div id="terminal">
          <TerminalBlock />
        </div>
        <div id="deploy">
          <DeploySection />
        </div>
        <Footer />
      </main>
    </>
  );
}
