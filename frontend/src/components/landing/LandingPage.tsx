import logoOrange from '../../assets/landing/logo-orange.png';
import arrowRight from '../../assets/landing/arrow-right.svg';
import { ThemeToggle } from '../common/ThemeToggle';
import { useTheme } from '../../hooks/useTheme';
import './LandingPage.css';

interface LandingPageProps {
  onEnter: () => void;
}

export function LandingPage({ onEnter }: LandingPageProps) {
  const [isDark, toggleTheme] = useTheme();

  return (
    <div className={`landing ${isDark ? 'landing--dark' : 'landing--light'}`}>
      <ThemeToggle isDark={isDark} onToggle={toggleTheme} />

      <main className="landing__content">
        <header className="landing__brand">
          <img className="landing__logo" src={logoOrange} alt="Logo JagaBorneo" />
          <h1 className="landing__title">JagaBorneo</h1>
        </header>

        <p className="landing__desc">
          Apa itu JagaBorneo? Lorem Ipsum is simply dummy text of the printing and typesetting
          industry. Lorem Ipsum has been the industry's standard dummy text ever since 1966, when
          designers at Letraset and James Mosley, the librarian at St Bride Printing Library in
          London, took a 1914 Cicero translation and scrambled it to make dummy text for Letraset's
          Body Type sheets. It has survived not only many decades, but also the leap into electronic
          typesetting, remaining essentially unchanged. It was popularised thanks to these sheets
          and more recently with desktop publishing software like Aldus PageMaker and Microsoft Word
          including versions of Lorem Ipsum.
        </p>

        <button type="button" className="landing__cta" onClick={onEnter}>
          <span>Masuk untuk lanjut</span>
          <img src={arrowRight} alt="" width={24} height={24} />
        </button>
      </main>
    </div>
  );
}

export default LandingPage;
