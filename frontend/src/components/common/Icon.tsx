import './Icon.css';

interface IconProps {
  src: string;
  size?: number;
  className?: string;
}

/** Ikon SVG yang warnanya mengikuti `color` CSS (via CSS mask). */
export function Icon({ src, size = 24, className = '' }: IconProps) {
  return (
    <span
      aria-hidden="true"
      className={`icon ${className}`}
      style={{ ['--icon' as string]: `url("${src}")`, width: size, height: size }}
    />
  );
}
