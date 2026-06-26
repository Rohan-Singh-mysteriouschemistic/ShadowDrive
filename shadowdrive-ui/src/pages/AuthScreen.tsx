import { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { useLocation, useNavigate } from 'react-router-dom';
import Input from '../components/Input';
import Button from '../components/Button';
import Card from '../components/Card';
import { setToken, CLIENT_API_URL } from '../lib/api';

const fadeIn = (delay: number) => ({
  initial:    { opacity: 0, y: 20 },
  animate:    { opacity: 1, y: 0 },
  transition: { duration: 0.6, ease: [0.16, 1, 0.3, 1] as [number, number, number, number], delay },
});

function formatErrorMessage(error: any): string {
  if (typeof error === 'string') {
    try {
      const parsed = JSON.parse(error);
      return formatErrorMessage(parsed);
    } catch {
      return error;
    }
  }
  
  if (typeof error === 'object' && error !== null) {
    if (error.detail) {
      return formatErrorMessage(error.detail);
    }
    if (Array.isArray(error)) {
      return error.map(err => {
        if (err.msg) {
          const field = err.loc ? err.loc[err.loc.length - 1] : '';
          return `${field ? field.toUpperCase() + ': ' : ''}${err.msg}`;
        }
        return JSON.stringify(err);
      }).join(', ');
    }
    return JSON.stringify(error);
  }
  
  return String(error);
}

export default function AuthScreen() {
  const location = useLocation();
  const [isLogin, setIsLogin] = useState(!location.search.includes('mode=deploy'));
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();

  const handleSubmit = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    setError(null);
    setLoading(true);

    const formData = new FormData(e.currentTarget);
    const email = formData.get('email') as string;
    const password = formData.get('password') as string;
    const passphrase = formData.get('passphrase') as string;

    if (!email) {
      setError("Identity [Email] is required.");
      setLoading(false);
      return;
    }

    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    if (!emailRegex.test(email)) {
      setError("Please enter a valid email address (e.g., user@example.com).");
      setLoading(false);
      return;
    }

    if (!password) {
      setError("Password is required.");
      setLoading(false);
      return;
    }

    if (!isLogin) {
      const confirmPassword = formData.get('confirm-password') as string;
      if (!confirmPassword) {
        setError("Please verify your password.");
        setLoading(false);
        return;
      }
      if (password !== confirmPassword) {
        setError("Passwords do not match.");
        setLoading(false);
        return;
      }
    }

    if (!passphrase) {
      setError("Encryption Passphrase is required. Please fill it to secure your vault.");
      setLoading(false);
      return;
    }

    try {
      const endpoint = isLogin ? `${CLIENT_API_URL}/api/auth/login` : `${CLIENT_API_URL}/api/auth/register`;
      const body = isLogin
        ? { email, password, passphrase }
        : { email, password, username: email.split('@')[0], passphrase };

      const response = await fetch(endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });

      if (!response.ok) {
        const errData = await response.json().catch(() => ({}));
        const detail = errData.detail;
        if (typeof detail === 'object') {
          throw new Error(JSON.stringify(detail));
        }
        throw new Error(detail || 'Authentication failed. Make sure the local Client Agent is running.');
      }

      const data = await response.json();

      if (data.access_token) {
        setToken(data.access_token);
      } else {
        setToken("local_client_authenticated");
      }

      navigate(location.search.includes('mode=deploy') ? '/nodes/deploy' : '/vault');
    } catch (err: any) {
      setError(formatErrorMessage(err.message || err));
    } finally {
      setLoading(false);
    }
  };

  const toggle = () => setIsLogin((prev) => !prev);

  return (
    <div className="w-full h-screen flex flex-col md:flex-row bg-background text-on-surface font-body-md text-body-md overflow-hidden selection:bg-primary/30 selection:text-primary">

      {/* LEFT PANEL — Branding (desktop only) */}
      <motion.div
        className="hidden md:flex w-1/2 bg-surface-container-lowest relative items-center justify-center p-margin-desktop border-r border-white/5 overflow-hidden"
        initial={{ opacity: 0, x: -40 }}
        animate={{ opacity: 1, x: 0 }}
        transition={{ duration: 0.8, ease: [0.16, 1, 0.3, 1] }}
      >
        <div className="absolute inset-0 bg-[radial-gradient(circle_at_center,rgba(16,185,129,0.05)_0%,transparent_50%)]" />
        <div
          className="absolute inset-0 opacity-[0.03] pointer-events-none"
          style={{
            backgroundImage: `url("data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSI4IiBoZWlnaHQ9IjgiPgo8cmVjdCB3aWR0aD0iOCIgaGVpZ2h0PSI4IiBmaWxsPSIjZmZmIiBmaWxsLW9wYWNpdHk9IjAuMDUiLz4KPHBhdGggZD0iTTAgMGg4djhIMHoiIGZpbGw9Im5vbmUiIHN0cm9rZT0iI2ZmZiIgc3Ryb2tlLW9wYWNpdHk9IjAuMSIgc3Ryb2tlLXdpZHRoPSIxIi8+Cjwvc3ZnPg==")`,
          }}
        />
        <motion.div className="relative z-10 text-center max-w-lg" {...fadeIn(0.2)}>
          <img src="/logo.png" alt="ShadowDrive Logo" className="w-16 h-16 object-contain mx-auto mb-8 filter drop-shadow-[0_0_15px_rgba(16,185,129,0.4)]" />
          <h1 className="text-white mb-4 tracking-tighter font-display-lg text-display-lg" style={{ textShadow: '0 0 20px rgba(16,185,129,0.4)' }}>
            SHADOWDRIVE
          </h1>
          <p className="font-code-sm text-code-sm text-on-surface-variant uppercase tracking-[0.2em]">
            Terminal-grade synchronization.
          </p>
        </motion.div>
      </motion.div>

      {/* RIGHT PANEL — Auth Form */}
      <div className="w-full md:w-1/2 bg-background relative flex flex-col items-center justify-center p-margin-mobile md:p-margin-desktop">
        <div className="w-full max-w-md">

          {/* Mobile branding fallback */}
          <motion.div className="md:hidden flex flex-col items-center text-center mb-10" {...fadeIn(0)}>
            <img src="/logo.png" alt="ShadowDrive Logo" className="w-12 h-12 object-contain mb-4 filter drop-shadow-[0_0_10px_rgba(16,185,129,0.4)]" />
            <h1 className="font-headline-lg-mobile text-headline-lg-mobile text-white tracking-tighter" style={{ textShadow: '0 0 20px rgba(16,185,129,0.4)' }}>
              SHADOWDRIVE
            </h1>
          </motion.div>

          <Card variant="glass" className="p-8 relative overflow-hidden group">
            <div className="absolute inset-0 bg-[radial-gradient(circle_at_top_right,rgba(16,185,129,0.08)_0%,transparent_60%)] opacity-0 group-hover:opacity-100 transition-opacity duration-700 pointer-events-none" />

            <div className="relative z-10">
              {/* Header */}
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
                <motion.p className="font-label-md text-label-md text-on-surface-variant" {...fadeIn(0.1)}>
                  Secure terminal connection required.
                </motion.p>
              </div>

              {/* Form */}
              <form className="space-y-6" onSubmit={handleSubmit} noValidate>
                <motion.div {...fadeIn(0.2)}>
                  <Input
                    id="email"
                    name="email"
                    label="IDENTITY [EMAIL]"
                    type="email"
                    placeholder="sysadmin@network.local"
                    icon="mail"
                  />
                </motion.div>

                <motion.div {...fadeIn(0.3)}>
                  <Input
                    id="password"
                    name="password"
                    label="PASSWORD"
                    type="password"
                    placeholder="••••••••••••"
                    icon="key"
                  />
                </motion.div>

                <motion.div {...fadeIn(0.35)}>
                  <Input
                    id="passphrase"
                    name="passphrase"
                    label="ENCRYPTION PASSPHRASE"
                    type="password"
                    placeholder="••••••••••••"
                    icon="enhanced_encryption"
                  />
                </motion.div>

                {/* Register-only field */}
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
                      <Input
                        id="confirm-password"
                        name="confirm-password"
                        label="VERIFY PASSWORD"
                        type="password"
                        placeholder="••••••••••••"
                        icon="lock_reset"
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
                  <Button
                    type="submit"
                    loading={loading}
                    icon="terminal"
                    className="w-full"
                    size="lg"
                  >
                    {loading ? 'AUTHENTICATING...' : isLogin ? 'EXECUTE // LOGIN' : 'EXECUTE // DEPLOY'}
                  </Button>
                </motion.div>
              </form>

              {/* Toggle link */}
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
          </Card>

          {/* Status bar */}
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
