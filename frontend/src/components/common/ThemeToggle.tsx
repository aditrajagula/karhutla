import lightModeIcon from '../../assets/landing/light-mode.svg';
import darkModeIcon from '../../assets/landing/dark-mode.svg';
import './ThemeToggle.css';

interface ThemeToggleProps {
  isDark: boolean;
  onToggle: () => void;
}

export function ThemeToggle({ isDark, onToggle }: ThemeToggleProps) {
  return (
    <button
      type="button"
      className={`theme-toggle ${isDark ? 'theme-toggle--dark' : ''}`}
      onClick={onToggle}
      aria-label={isDark ? 'Ganti ke mode terang' : 'Ganti ke mode gelap'}
    >
      <span
        className="theme-toggle__hint"
        aria-hidden="true"
        style={{ ['--icon' as string]: `url("${isDark ? lightModeIcon : darkModeIcon}")` }}
      />
      <span className="theme-toggle__knob">
        {isDark ? (
          <span
            className="theme-toggle__icon"
            style={{ ['--icon' as string]: `url("${darkModeIcon}")` }}
          />
        ) : (
          <img src={lightModeIcon} alt="" width={24} height={24} />
        )}
      </span>
    </button>
  );
}
