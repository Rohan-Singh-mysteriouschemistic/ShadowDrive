// @ts-nocheck
import { useEffect } from 'react';
import { useNavigate } from 'react-router-dom';

export default function LandingPage() {
  const navigate = useNavigate();
  useEffect(() => {
    // --- Reveal Animations (Intersection Observer) ---
    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            entry.target.classList.add('is-visible');
          }
        });
      },
      { threshold: 0.1, rootMargin: '0px 0px -50px 0px' }
    );
    document.querySelectorAll('.reveal-up').forEach((el) => observer.observe(el));

    // Feature Cards Staggered Reveal
    const featureObserver = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            entry.target.querySelectorAll('.feature-card-reveal').forEach((card) => {
              card.classList.add('is-active');
            });
            featureObserver.unobserve(entry.target);
          }
        });
      },
      { threshold: 0.1 }
    );
    const featureGrid = document.getElementById('feature-grid');
    if (featureGrid) featureObserver.observe(featureGrid);

    // Force-reveal anything already in viewport on mount
    setTimeout(() => {
      document.querySelectorAll('.reveal-up').forEach((el) => {
        const rect = el.getBoundingClientRect();
        if (rect.top < window.innerHeight) el.classList.add('is-visible');
      });
      // Also force-reveal feature cards if already in view
      if (featureGrid) {
        const rect = featureGrid.getBoundingClientRect();
        if (rect.top < window.innerHeight) {
          featureGrid.querySelectorAll('.feature-card-reveal').forEach((card) => {
            card.classList.add('is-active');
          });
        }
      }
    }, 150);

    // --- 3D Tilt Effect for Cards ---
    const cards = document.querySelectorAll('.tilt-card');
    const tiltHandlers = [];
    cards.forEach((card) => {
      const onMove = (e) => {
        const rect = card.getBoundingClientRect();
        const x = e.clientX - rect.left;
        const y = e.clientY - rect.top;
        const cx = rect.width / 2;
        const cy = rect.height / 2;
        const rotX = ((y - cy) / cy) * -10;
        const rotY = ((x - cx) / cx) * 10;
        card.style.transform = `perspective(1000px) rotateX(${rotX}deg) rotateY(${rotY}deg) scale3d(1.02,1.02,1.02)`;
      };
      const onLeave = () => {
        card.style.transform = 'perspective(1000px) rotateX(0) rotateY(0) scale3d(1,1,1)';
      };
      card.addEventListener('mousemove', onMove);
      card.addEventListener('mouseleave', onLeave);
      tiltHandlers.push({ card, onMove, onLeave });
    });

    // --- Three.js Particle Constellation ---
    let renderer = null;
    function initThreeJS() {
      const container = document.getElementById('canvas-container');
      if (!container) return;
      const scene = new THREE.Scene();
      const camera = new THREE.PerspectiveCamera(75, window.innerWidth / window.innerHeight, 0.1, 2000);
      camera.position.z = 150;

      renderer = new THREE.WebGLRenderer({ alpha: true, antialias: true });
      renderer.setSize(window.innerWidth, window.innerHeight);
      renderer.setPixelRatio(window.devicePixelRatio);
      container.appendChild(renderer.domElement);

      const particlesGeometry = new THREE.BufferGeometry();
      const count = 4500;
      const posArray = new Float32Array(count * 3);
      for (let i = 0; i < count * 3; i++) posArray[i] = (Math.random() - 0.5) * 600;
      particlesGeometry.setAttribute('position', new THREE.BufferAttribute(posArray, 3));

      const material = new THREE.PointsMaterial({
        size: 0.8,
        color: 0x10b981,
        transparent: true,
        opacity: 0.4,
        blending: THREE.AdditiveBlending,
      });
      const mesh = new THREE.Points(particlesGeometry, material);
      scene.add(mesh);

      let mouseX = 0, mouseY = 0;
      const halfX = window.innerWidth / 2;
      const halfY = window.innerHeight / 2;
      const onMouseMove = (e) => {
        mouseX = e.clientX - halfX;
        mouseY = e.clientY - halfY;
      };
      document.addEventListener('mousemove', onMouseMove);

      const clock = new THREE.Clock();
      function animate() {
        requestAnimationFrame(animate);
        const t = clock.getElapsedTime();
        mesh.rotation.y = t * 0.03;
        mesh.rotation.x = t * 0.01;
        mesh.rotation.y += 0.05 * (mouseX * 0.0008 - mesh.rotation.y);
        mesh.rotation.x += 0.05 * (mouseY * 0.0008 - mesh.rotation.x);
        renderer.render(scene, camera);
      }
      animate();

      const onResize = () => {
        camera.aspect = window.innerWidth / window.innerHeight;
        camera.updateProjectionMatrix();
        renderer.setSize(window.innerWidth, window.innerHeight);
      };
      window.addEventListener('resize', onResize);
    }

    if (typeof THREE !== 'undefined') initThreeJS();

    return () => {
      observer.disconnect();
      featureObserver.disconnect();
      tiltHandlers.forEach(({ card, onMove, onLeave }) => {
        card.removeEventListener('mousemove', onMove);
        card.removeEventListener('mouseleave', onLeave);
      });
      if (renderer) {
        const container = document.getElementById('canvas-container');
        if (container && renderer.domElement) container.removeChild(renderer.domElement);
        renderer.dispose();
      }
    };
  }, []);

  return (
    <div className="bg-background text-on-surface font-body-md antialiased min-h-screen flex flex-col relative overflow-x-hidden">

      {/* 3D Canvas Background */}
      <div id="canvas-container" style={{
        position: 'fixed', top: 0, left: 0,
        width: '100vw', height: '100vh',
        zIndex: 0, pointerEvents: 'none'
      }}></div>

      {/* Ambient Orbs */}
      <div style={{
        position: 'fixed', borderRadius: '50%',
        background: 'radial-gradient(circle, rgba(16,185,129,0.15) 0%, transparent 70%)',
        filter: 'blur(60px)', pointerEvents: 'none', zIndex: 1,
        animation: 'float 20s ease-in-out infinite alternate',
        top: '-100px', left: '-100px', width: '600px', height: '600px'
      }}></div>
      <div style={{
        position: 'fixed', borderRadius: '50%',
        background: 'radial-gradient(circle, rgba(16,185,129,0.15) 0%, transparent 70%)',
        filter: 'blur(60px)', pointerEvents: 'none', zIndex: 1,
        animation: 'float 20s ease-in-out infinite alternate',
        animationDelay: '-10s',
        bottom: '-200px', right: '-100px', width: '800px', height: '800px'
      }}></div>

      {/* Content Wrapper */}
      <div style={{ position: 'relative', zIndex: 10 }} className="flex flex-col min-h-screen">

        {/* Header */}
        <header className="fixed top-0 w-full z-50 flex justify-between items-center px-8 md:px-12 py-8 hidden md:flex reveal-up is-visible" style={{ animationDelay: '0.1s' }}>
          <div className="flex items-center gap-2 cursor-pointer">
            <span className="font-display-lg text-[22px] font-bold text-white tracking-tight">ShadowDrive.</span>
          </div>
          <nav className="flex items-center gap-8">
            <button 
              onClick={() => navigate('/auth')} 
              className="text-[13px] font-bold tracking-widest uppercase text-white/70 hover:text-white transition-colors duration-200"
            >
              Login
            </button>
          </nav>
        </header>

        {/* Mobile Nav */}
        <header className="fixed top-0 w-full z-50 flex justify-between items-center px-4 h-16 bg-background/60 backdrop-blur-md border-b border-white/5 md:hidden reveal-up is-visible">
          <span className="text-xl font-bold text-primary tracking-tighter" style={{ fontFamily: 'Geist, sans-serif' }}>ShadowDrive</span>
          <button className="text-on-surface p-2">
            <span className="material-symbols-outlined">menu</span>
          </button>
        </header>

        {/* Main */}
        <main className="flex-grow pt-24 w-full max-w-[1440px] mx-auto relative px-4 md:px-12">

          {/* Hero */}
          <section className="relative pt-12 pb-20 lg:pt-16 lg:pb-32 flex flex-col items-start text-left max-w-[800px] z-10">
            
            {/* Liquid Glass Card (from demo) */}
            <div className="reveal-up is-visible liquid-glass w-[210px] h-[210px] rounded-2xl p-5 flex flex-col justify-between mb-8 cursor-pointer tilt-card z-20" style={{
              transitionDelay: '100ms'
            }}>
              <div className="text-[11px] font-medium text-white/50 tracking-widest" style={{ fontFamily: 'Geist, sans-serif' }}>
                [ NODE_ACTIVE ]
              </div>
              <div className="space-y-1">
                <h3 className="text-[15px] leading-[1.2] font-medium text-on-surface" style={{ fontFamily: 'Geist, sans-serif' }}>
                  Decentralized <span className="italic font-normal text-[19px] text-primary block mt-0.5">P2P Sync</span>
                </h3>
                <p className="text-[10.5px] text-on-surface-variant leading-relaxed" style={{ fontFamily: 'Geist, sans-serif' }}>
                  Cryptographically secure, zero-trust data replication.
                </p>
              </div>
            </div>
            
            <h1 className="reveal-up is-visible emerald-text-glow mb-6 uppercase tracking-tight" style={{
              fontFamily: 'Geist, sans-serif',
              fontSize: '56px', lineHeight: '1.05', fontWeight: 800,
              transitionDelay: '300ms'
            }}>
              SYNCHRONIZATION,<br/>PERFECTED<span className="text-primary">.</span>
            </h1>
            
            <p className="reveal-up is-visible text-on-surface-variant mb-10 max-w-[600px]" style={{
              fontFamily: 'Geist, sans-serif', fontSize: '16px', lineHeight: '1.6',
              transitionDelay: '400ms'
            }}>
              A production-grade distributed file system. Zero conflicts. Absolute truth. Secure your data with our robust architecture built to ensure high availability and seamless synchronization across your entire network.
            </p>
            
            <div className="flex flex-col sm:flex-row gap-6 items-start reveal-up is-visible" style={{ animationDelay: '400ms' }}>
              <button 
                onClick={() => navigate('/auth?mode=deploy')} 
                className="flex items-center justify-center gap-3 bg-primary text-on-primary rounded-full px-8 py-4 font-bold uppercase tracking-wide hover:opacity-90 transition-opacity duration-200 group"
              >
                Get Started
                <span className="material-symbols-outlined text-[20px] group-hover:translate-x-1 transition-transform duration-300">arrow_forward</span>
              </button>
            </div>
          </section>

          {/* Feature Grid */}
          <section className="py-20 z-10 relative">
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6" id="feature-grid">
              {[
                {
                  icon: 'join_inner',
                  title: 'SHA-256 Deduplication',
                  desc: 'Never upload the same bytes twice. Our intelligent chunking algorithm ensures identical data is deduplicated at the block level before transmission.',
                  cmd: '> hash_check --strict',
                  delay: '100ms'
                },
                {
                  icon: 'alt_route',
                  title: 'Last-Write-Wins',
                  desc: 'Algorithmic conflict resolution leveraging logical clocks. Concurrent edits are deterministically resolved without manual intervention.',
                  cmd: '> sync_resolve --auto',
                  delay: '250ms'
                },
                {
                  icon: 'cloud_sync',
                  title: 'MinIO Object Storage',
                  desc: 'Chunk-based streaming to S3-compatible endpoints. High-throughput data ingress/egress optimized for distributed architectures.',
                  cmd: '> stream_s3 --chunk=8M',
                  delay: '400ms'
                }
              ].map(({ icon, title, desc, cmd, delay }) => (
                <div key={title}
                  className="tilt-card feature-card-reveal group flex flex-col items-start gap-5 h-full p-8 rounded-xl"
                  style={{
                    transitionDelay: delay,
                    background: 'rgba(17,17,17,0.6)',
                    backdropFilter: 'blur(20px)',
                    border: '1px solid rgba(255,255,255,0.05)',
                    transition: 'opacity 0.7s cubic-bezier(0.16,1,0.3,1), transform 0.7s cubic-bezier(0.16,1,0.3,1), box-shadow 0.3s'
                  }}
                >
                  <div className="w-12 h-12 rounded flex items-center justify-center text-primary group-hover:bg-primary/10 transition-colors duration-300 mb-2" style={{ background: '#18181b', border: '1px solid rgba(255,255,255,0.05)' }}>
                    <span className="material-symbols-outlined">{icon}</span>
                  </div>
                  <h3 className="text-on-surface" style={{ fontFamily: 'Geist, sans-serif', fontSize: '24px', fontWeight: 600, lineHeight: '1.3' }}>{title}</h3>
                  <p className="text-on-surface-variant flex-grow mt-2" style={{ fontFamily: 'Geist, sans-serif', fontSize: '16px', lineHeight: '1.6' }}>{desc}</p>
                  <div className="text-primary/80 px-3 py-1.5 rounded mt-6 self-start border border-primary/10 w-full overflow-x-auto whitespace-nowrap" style={{
                    fontFamily: 'JetBrains Mono, monospace', fontSize: '13px',
                    background: 'rgba(0,0,0,0.5)'
                  }}>
                    {cmd}
                  </div>
                </div>
              ))}
            </div>
          </section>

          {/* Topology Viz */}
          <section className="py-12 md:py-24 z-10 relative reveal-up is-visible" style={{ transitionDelay: '900ms' }}>
            <div className="w-full h-[400px] rounded-xl overflow-hidden relative" style={{
              background: 'rgba(0,0,0,0.4)',
              border: '1px solid rgba(255,255,255,0.1)',
              backdropFilter: 'blur(20px)'
            }}>
              <div style={{
                position: 'absolute', inset: 0,
                backgroundImage: "url('https://www.transparenttextures.com/patterns/carbon-fibre.png')",
                opacity: 0.1, mixBlendMode: 'overlay'
              }}></div>
              <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 text-center z-10 flex flex-col items-center">
                <span className="material-symbols-outlined text-primary mb-6 topology-icon" style={{ fontSize: '72px' }}>hub</span>
                <p className="text-primary uppercase opacity-80" style={{
                  fontFamily: 'JetBrains Mono, monospace', fontSize: '14px',
                  letterSpacing: '0.3em'
                }}>[ System Topology Visualization ]</p>
              </div>
              {/* Decorative code lines */}
              <div className="absolute top-6 left-6 flex flex-col gap-2" style={{ fontFamily: 'JetBrains Mono, monospace', fontSize: '13px', color: 'rgba(16,185,129,0.4)' }}>
                <span>&gt; INITIALIZING NODE CLUSTER...</span>
                <span>&gt; ESTABLISHING SECURE TUNNEL...</span>
                <span className="animate-pulse">&gt; WAITING FOR PEERS...</span>
              </div>
              {/* Grid overlay */}
              <div style={{
                position: 'absolute', inset: 0, pointerEvents: 'none',
                backgroundImage: 'linear-gradient(rgba(16,185,129,0.03) 1px, transparent 1px), linear-gradient(90deg, rgba(16,185,129,0.03) 1px, transparent 1px)',
                backgroundSize: '20px 20px'
              }}></div>
            </div>
          </section>

        </main>

        {/* Footer */}
        <footer className="w-full py-12 px-8 md:px-12 flex flex-col md:flex-row justify-between items-center gap-6 border-t border-white/5 mt-auto backdrop-blur-md relative z-10 reveal-up is-visible"
          style={{ background: 'rgba(24,24,27,0.5)', transitionDelay: '1000ms' }}>
          <div className="text-on-surface font-bold tracking-tight" style={{ fontFamily: 'Geist, sans-serif', fontSize: '20px' }}>ShadowDrive</div>
          <div className="text-on-surface-variant text-center md:text-left" style={{ fontFamily: 'JetBrains Mono, monospace', fontSize: '14px' }}>
            © 2026 ShadowDrive Systems. Terminal-grade synchronization.
          </div>
        </footer>

      </div>
    </div>
  );
}
