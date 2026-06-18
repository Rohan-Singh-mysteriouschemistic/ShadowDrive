import { useState, type InputHTMLAttributes } from 'react';

interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  icon?: string;
  error?: string;
}

export default function Input({
  label,
  icon,
  error,
  id,
  className = '',
  type = 'text',
  ...rest
}: InputProps) {
  const [showPassword, setShowPassword] = useState(false);
  const isPassword = type === 'password';
  const resolvedType = isPassword && showPassword ? 'text' : type;

  return (
    <div>
      {label && (
        <label
          htmlFor={id}
          className="block font-code-sm text-code-sm text-on-surface-variant mb-2 ml-1 tracking-widest uppercase"
        >
          {label}
        </label>
      )}
      <div className="relative">
        {icon && (
          <span className="absolute inset-y-0 left-0 flex items-center pl-3 text-on-surface-variant pointer-events-none">
            <span className="material-symbols-outlined" style={{ fontSize: '18px' }}>
              {icon}
            </span>
          </span>
        )}
        <input
          id={id}
          type={resolvedType}
          className={`
            w-full bg-surface-container-lowest border rounded-lg
            py-3 ${icon ? 'pl-10' : 'pl-4'} ${isPassword ? 'pr-10' : 'pr-4'}
            text-white font-code-sm text-code-sm
            focus:outline-none transition-all duration-300
            placeholder:text-on-surface-variant/50
            focus:border-primary focus:shadow-[0_0_15px_rgba(16,185,129,0.3)]
            ${error ? 'border-error' : 'border-white/10'}
            ${className}
          `}
          {...rest}
        />
        {isPassword && (
          <button
            type="button"
            onClick={() => setShowPassword(!showPassword)}
            className="absolute inset-y-0 right-0 flex items-center pr-3 text-on-surface-variant hover:text-primary focus:outline-none cursor-pointer"
          >
            <span className="material-symbols-outlined" style={{ fontSize: '18px' }}>
              {showPassword ? 'visibility_off' : 'visibility'}
            </span>
          </button>
        )}
      </div>
      {error && (
        <p className="text-error font-code-sm text-xs mt-1 ml-1">{error}</p>
      )}
    </div>
  );
}
