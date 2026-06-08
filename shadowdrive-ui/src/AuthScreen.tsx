import { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { useLocation, useNavigate } from 'react-router-dom';

// ---------------------------------------------------------------------------
// Reusable fade-up props generator (avoids Variants typing issue with `custom`)
// ---------------------------------------------------------------------------
const fadeIn = (delay: number) => ({
  initial:    { opacity: 0, y: 20 },
  animate:    { opacity: 1, y: 0 },
  transition: { duration: 0.6, ease: [0.16, 1, 0.3, 1] as [number, number, number, number], delay },
});

// ---------------------------------------------------------------------------
// Input field sub-component
// ---------------------------------------------------------------------------
interface InputFieldProps {
  id: string;
  label: string;
  type: string;
  placeholder: string;
  icon: string;
  required?: boolean;
  delay: number;
  name: string;
  toggleVisibility?: () => void;
  showPassword?: boolean;
}

function InputField({ id, label, type, placeholder, icon, required = true, delay, name, toggleVisibility, showPassword }: InputFieldProps) {
  return (
    <motion.div {...fadeIn(delay)}>
      <label
        htmlFor={id}
        className="block font-code-sm text-code-sm text-on-surface-variant mb-2 ml-1 tracking-widest uppercase"
      >
        {label}
      </label>
      <div className="relative">
        <span className="absolute inset-y-0 left-0 flex items-center pl-3 text-on-surface-variant pointer-events-none">
          <span className="material-symbols-outlined" style={{ fontSize: '18px' }}>{icon}</span>
        </span>
        <input
          id={id}
          name={name}
          type={type}
          placeholder={placeholder}
          required={required}
          className="
            w-full bg-surface-container-lowest border border-white/10 rounded-lg
            py-3 pl-10 pr-10 text-white font-code-sm text-code-sm
            focus:outline-none transition-all duration-300
            placeholder:text-on-surface-variant/50
            focus:border-primary focus:shadow-[0_0_15px_rgba(16,185,129,0.3)]
          "
        />
        {toggleVisibility && (
          <button
            type="button"
            onClick={toggleVisibility}
            className="absolute inset-y-0 right-0 flex items-center pr-3 text-on-surface-variant hover:text-primary focus:outline-none"
          >
            <span className="material-symbols-outlined" style={{ fontSize: '18px' }}>
              {showPassword ? 'visibility_off' : 'visibility'}
            </span>
          </button>
        )}
      </div>
    </motion.div>
  );
}

// ---------------------------------------------------------------------------
// Main AuthScreen component
// ---------------------------------------------------------------------------
export default function AuthScreen() {
  const location = useLocation();
  const [isLogin, setIsLogin] = useState(!location.search.includes('mode=deploy'));
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  const navigate = useNavigate();

  const handleSubmit = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    setError(null);
    setLoading(true);

    const formData = new FormData(e.currentTarget);
    const email = formData.get('email') as string;
    const password = formData.get('password') as string;
    const passphrase = formData.get('passphrase') as string;
    const username = !isLogin ? email.split('@')[0] : "";

    try {
      const endpoint = isLogin ? 'http://127.0.0.1:8001/api/auth/login' : 'http://127.0.0.1:8001/api/auth/register';
      const body = isLogin 
        ? { email, password, passphrase }
        : { email, password, username, passphrase };

      const response = await fetch(endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });

      if (!response.ok) {
        const errData = await response.json().catch(() => ({}));
        throw new Error(errData.detail || 'Authentication failed. Make sure the local Client Agent is running.');
      }

      const data = await response.json();
      
      // The local API handles getting and saving the token in the backend DB!
      // But we also need the token in the UI so we can fetch files directly.
      if (data.access_token) {
        localStorage.setItem('shadowdrive_token', data.access_token);
      } else {
        localStorage.setItem('shadowdrive_token', "local_client_authenticated");
      }
      
      if (location.search.includes('mode=deploy')) {
        navigate('/nodes/deploy');
      } else {
        navigate('/vault');
      }
    } catch (err: any) {
      setError(err.message || 'An error occurred during authentication.');
    } finally {
      setLoading(false);
    }
  };

  const toggle = () => setIsLogin((prev) => !prev);

  return (
    <div className="w-full h-screen flex flex-col md:flex-row bg-background text-on-surface font-body-md text-body-md overflow-hidden selection:bg-primary/30 selection:text-primary">

      {/* ================================================================
          LEFT PANEL — Branding (desktop only)
      ================================================================ */}
      <motion.div
        className="hidden md:flex w-1/2 bg-surface-container-lowest relative items-center justify-center p-margin-desktop border-r border-white/5 overflow-hidden"
        initial={{ opacity: 0, x: -40 }}
        animate={{ opacity: 1, x: 0 }}
        transition={{ duration: 0.8, ease: [0.16, 1, 0.3, 1] }}
      >
        {/* Radial emerald glow */}
        <div className="absolute inset-0 bg-[radial-gradient(circle_at_center,rgba(16,185,129,0.05)_0%,transparent_50%)]" />

        {/* Subtle dot-grid texture */}
        <div
          className="absolute inset-0 opacity-[0.03] pointer-events-none"
          style={{
            backgroundImage: `url("data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSI4IiBoZWlnaHQ9IjgiPgo8cmVjdCB3aWR0aD0iOCIgaGVpZ2h0PSI4IiBmaWxsPSIjZmZmIiBmaWxsLW9wYWNpdHk9IjAuMDUiLz4KPHBhdGggZD0iTTAgMGg4djhIMHoiIGZpbGw9Im5vbmUiIHN0cm9rZT0iI2ZmZiIgc3Ryb2tlLW9wYWNpdHk9IjAuMSIgc3Ryb2tlLXdpZHRoPSIxIi8+Cjwvc3ZnPg==")`,
          }}
        />

        {/* Branding content */}
        <motion.div
          className="relative z-10 text-center max-w-lg"
          {...fadeIn(0.2)}
        >
          <div className="inline-flex items-center justify-center w-16 h-16 rounded-lg bg-surface-container border border-white/10 mb-8 text-primary shadow-[0_0_30px_rgba(16,185,129,0.2)]">
            <span
              className="material-symbols-outlined text-4xl"
              style={{ fontVariationSettings: '"FILL" 1', fontSize: '36px' }}
            >
              terminal
            </span>
          </div>
          <h1
            className="text-white mb-4 tracking-tighter font-display-lg text-display-lg"
            style={{ textShadow: '0 0 20px rgba(16,185,129,0.4)' }}
          >
            SHADOWDRIVE
          </h1>
          <p className="font-code-sm text-code-sm text-on-surface-variant uppercase tracking-[0.2em]">
            Terminal-grade synchronization.
          </p>
        </motion.div>
      </motion.div>

      {/* ================================================================
          RIGHT PANEL — Auth Form
      ================================================================ */}
      <div className="w-full md:w-1/2 bg-background relative flex flex-col items-center justify-center p-margin-mobile md:p-margin-desktop">
        <div className="w-full max-w-md">

          {/* Mobile branding fallback */}
          <motion.div className="md:hidden text-center mb-10" {...fadeIn(0)}>
            <h1
              className="font-headline-lg-mobile text-headline-lg-mobile text-white tracking-tighter"
              style={{ textShadow: '0 0 20px rgba(16,185,129,0.4)' }}
            >
              SHADOWDRIVE
            </h1>
          </motion.div>

          {/* Glass card */}
          <div
            className="rounded-xl p-8 shadow-2xl relative overflow-hidden group"
            style={{
              background: 'rgba(17,17,17,0.6)',
              backdropFilter: 'blur(20px)',
              WebkitBackdropFilter: 'blur(20px)',
              border: '1px solid rgba(255,255,255,0.05)',
            }}
          >
            {/* Card hover radial glow */}
            <div className="absolute inset-0 bg-[radial-gradient(circle_at_top_right,rgba(16,185,129,0.08)_0%,transparent_60%)] opacity-0 group-hover:opacity-100 transition-opacity duration-700 pointer-events-none" />

            <div className="relative z-10">

              {/* ----- Header (animates on mode switch) ----- */}
              <div className="mb-8 text-center">
                <AnimatePresence mode="wait">
                  <motion.h2
                    key={isLogin ? 'login-title' : 'register-title'}
                    className="font-headline-md text-headline-md text-white mb-2"
                    initial={{ opacity: 0, y: -10 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, y: 10 }}
                    transition={{ duration: 0.25 }}
                  >
                    {isLogin ? 'Access Vault' : 'Initialize Node'}
                  </motion.h2>
                </AnimatePresence>
                <motion.p
                  className="font-label-md text-label-md text-on-surface-variant"
                  {...fadeIn(0.1)}
                >
                  Secure terminal connection required.
                </motion.p>
              </div>

              {/* ----- Form ----- */}
              <form className="space-y-6" onSubmit={handleSubmit} noValidate>

                <InputField
                  id="email"
                  name="email"
                  label="IDENTITY [EMAIL]"
                  type="email"
                  placeholder="sysadmin@network.local"
                  icon="mail"
                  delay={0.2}
                />

                <InputField
                  id="password"
                  name="password"
                  label="PASSWORD"
                  type={showPassword ? 'text' : 'password'}
                  placeholder="••••••••••••"
                  icon="key"
                  delay={0.3}
                  toggleVisibility={() => setShowPassword(!showPassword)}
                  showPassword={showPassword}
                />

                <InputField
                  id="passphrase"
                  name="passphrase"
                  label="ENCRYPTION PASSPHRASE"
                  type={showPassword ? 'text' : 'password'}
                  placeholder="••••••••••••"
                  icon="enhanced_encryption"
                  delay={0.35}
                  toggleVisibility={() => setShowPassword(!showPassword)}
                  showPassword={showPassword}
                />

                {/* Register-only field — conditionally rendered, NOT hidden */}
                <AnimatePresence>
                  {!isLogin && (
                    <motion.div
                      key="confirm-password"
                      initial={{ opacity: 0, height: 0, y: -8 }}
                      animate={{ opacity: 1, height: 'auto', y: 0 }}
                      exit={{ opacity: 0, height: 0, y: -8 }}
                      transition={{ duration: 0.35, ease: [0.16, 1, 0.3, 1] }}
                      style={{ overflow: 'hidden' }}
                    >
                      <InputField
                        id="confirm-password"
                        name="confirm-password"
                        label="VERIFY PASSWORD"
                        type={showPassword ? 'text' : 'password'}
                        placeholder="••••••••••••"
                        icon="lock_reset"
                        delay={0}
                        toggleVisibility={() => setShowPassword(!showPassword)}
                        showPassword={showPassword}
                      />
                    </motion.div>
                  )}
                </AnimatePresence>

                {/* Error Message */}
                <AnimatePresence>
                  {error && (
                    <motion.div
                      initial={{ opacity: 0, y: -10 }}
                      animate={{ opacity: 1, y: 0 }}
                      exit={{ opacity: 0, y: -10 }}
                      className="text-red-500 font-code-sm text-sm text-center bg-red-500/10 py-2 rounded border border-red-500/20"
                    >
                      {error}
                    </motion.div>
                  )}
                </AnimatePresence>

                {/* Submit button */}
                <motion.div className="pt-2" {...fadeIn(0.4)}>
                  <button
                    type="submit"
                    disabled={loading}
                    className="
                      w-full bg-surface-container border border-primary/30 text-primary
                      font-label-md text-label-md py-3 px-4 rounded-lg
                      flex items-center justify-center gap-2
                      hover:bg-primary hover:text-surface-container-lowest
                      transition-all duration-300 group/btn
                      shadow-[0_0_15px_rgba(16,185,129,0.1)]
                      hover:shadow-[0_0_20px_rgba(16,185,129,0.4)]
                    "
                  >
                    <span className="material-symbols-outlined group-hover/btn:animate-pulse" style={{ fontSize: '18px' }}>
                      terminal
                    </span>
                    <AnimatePresence mode="wait">
                      <motion.span
                        key={isLogin ? 'btn-login' : 'btn-register'}
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        exit={{ opacity: 0 }}
                        transition={{ duration: 0.15 }}
                      >
                        {loading ? 'AUTHENTICATING...' : isLogin ? 'EXECUTE // LOGIN' : 'EXECUTE // DEPLOY'}
                      </motion.span>
                    </AnimatePresence>
                  </button>
                </motion.div>
              </form>

              {/* ----- Toggle link ----- */}
              <motion.div className="mt-8 text-center" {...fadeIn(0.5)}>
                <button
                  onClick={toggle}
                  className="font-code-sm text-code-sm text-on-surface-variant hover:text-primary transition-colors duration-200"
                >
                  <AnimatePresence mode="wait">
                    <motion.span
                      key={isLogin ? 'toggle-login' : 'toggle-register'}
                      initial={{ opacity: 0 }}
                      animate={{ opacity: 1 }}
                      exit={{ opacity: 0 }}
                      transition={{ duration: 0.15 }}
                    >
                      {isLogin ? (
                        <>
                          New to the protocol?{' '}
                          <span className="text-white underline underline-offset-4 decoration-white/30 hover:decoration-primary transition-all">
                            Sign-Up
                          </span>
                        </>
                      ) : (
                        <>
                          Already registered?{' '}
                          <span className="text-white underline underline-offset-4 decoration-white/30 hover:decoration-primary transition-all">
                            Access vault.
                          </span>
                        </>
                      )}
                    </motion.span>
                  </AnimatePresence>
                </button>
              </motion.div>

            </div>
          </div>

          {/* ----- Status bar ----- */}
          <motion.div className="mt-8 text-center opacity-50" {...fadeIn(0.6)}>
            <p className="font-code-sm text-on-surface-variant" style={{ fontSize: '10px' }}>
              STATUS:{' '}
              <span className="text-primary animate-pulse inline-block w-2 h-2 rounded-full bg-primary mx-1 align-middle" />
              {' '}ONLINE // SYSTEM OPERATIONAL
            </p>
          </motion.div>

        </div>
      </div>
    </div>
  );
}
