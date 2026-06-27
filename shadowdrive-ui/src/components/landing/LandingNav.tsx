"use client";
import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import { ShadowDriveLogo } from '../shared/ShadowDriveLogo';
import Button from '../Button';

export default function LandingNav() {
  const [scrolled, setScrolled] = useState(false);
  const [hidden, setHidden] = useState(false);
  const [lastScrollY, setLastScrollY] = useState(0);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const navigate = useNavigate();

  useEffect(() => {
    const handleScroll = () => {
      const currentScrollY = window.scrollY;
      
      // Toggle glass background
      if (currentScrollY > 50) {
        setScrolled(true);
      } else {
        setScrolled(false);
      }

      // Hide on scroll down, show on scroll up
      if (currentScrollY > lastScrollY && currentScrollY > 200) {
        setHidden(true);
        setMobileMenuOpen(false); // Close mobile menu if open
      } else {
        setHidden(false);
      }

      setLastScrollY(currentScrollY);
    };

    window.addEventListener('scroll', handleScroll, { passive: true });
    return () => window.removeEventListener('scroll', handleScroll);
  }, [lastScrollY]);

  const scrollToSection = (id: string) => {
    const el = document.getElementById(id);
    if (el) {
      el.scrollIntoView({ behavior: 'smooth' });
      setMobileMenuOpen(false);
    }
  };

  const navLinks = [
    { label: 'Features', id: 'features' },
    { label: 'Terminal', id: 'terminal' },
    { label: 'Deploy', id: 'deploy' },
  ];

  return (
    <motion.header
      initial={{ y: -100 }}
      animate={{ y: hidden ? -100 : 0 }}
      transition={{ duration: 0.3, ease: 'easeInOut' }}
      className={`fixed top-0 left-0 right-0 z-50 transition-colors duration-300 ${
        scrolled 
          ? 'bg-background/80 backdrop-blur-md border-b border-white/5 shadow-lg' 
          : 'bg-transparent border-transparent'
      }`}
    >
      <div className="max-w-7xl mx-auto px-6 md:px-12 lg:px-16 h-20 flex items-center justify-between">
        
        {/* Logo area */}
        <div 
          className="flex items-center gap-3 cursor-pointer group"
          onClick={() => window.scrollTo({ top: 0, behavior: 'smooth' })}
        >
          <ShadowDriveLogo size={32} animated={false} />
          <span className="font-headline-md text-[1.25rem] font-bold tracking-tighter text-white group-hover:text-primary transition-colors duration-300">
            SHADOWDRIVE
          </span>
        </div>

        {/* Desktop Links */}
        <nav className="hidden md:flex items-center gap-8">
          {navLinks.map((link) => (
            <button
              key={link.id}
              onClick={() => scrollToSection(link.id)}
              className="text-sm font-label-md text-on-surface-variant hover:text-white transition-colors uppercase tracking-wider"
            >
              {link.label}
            </button>
          ))}
        </nav>

        {/* Desktop CTA */}
        <div className="hidden md:flex items-center gap-4">
          <button 
            onClick={() => navigate('/auth')}
            className="text-sm font-label-md text-white hover:text-primary transition-colors uppercase tracking-wider px-2"
          >
            Access Vault
          </button>
          <Button 
            onClick={() => navigate('/auth?mode=deploy')}
            size="md"
            icon="terminal"
          >
            Deploy Node
          </Button>
        </div>

        {/* Mobile menu toggle */}
        <button 
          className="md:hidden text-white p-2"
          onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
        >
          <span className="material-symbols-outlined text-[24px]">
            {mobileMenuOpen ? 'close' : 'menu'}
          </span>
        </button>
      </div>

      {/* Mobile Menu Dropdown */}
      <AnimatePresence>
        {mobileMenuOpen && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }}
            className="md:hidden bg-surface-container-lowest border-b border-white/5 overflow-hidden"
          >
            <div className="px-6 py-4 flex flex-col gap-4">
              {navLinks.map((link) => (
                <button
                  key={link.id}
                  onClick={() => scrollToSection(link.id)}
                  className="text-left py-2 text-on-surface hover:text-primary font-label-md uppercase tracking-wider transition-colors"
                >
                  {link.label}
                </button>
              ))}
              <div className="h-[1px] w-full bg-white/5 my-2" />
              <button
                onClick={() => { navigate('/auth'); setMobileMenuOpen(false); }}
                className="text-left py-2 text-on-surface hover:text-primary font-label-md uppercase tracking-wider transition-colors"
              >
                Access Vault
              </button>
              <button
                onClick={() => { navigate('/auth?mode=deploy'); setMobileMenuOpen(false); }}
                className="text-left py-2 text-primary font-label-md uppercase tracking-wider transition-colors font-bold"
              >
                Deploy Node
              </button>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.header>
  );
}
