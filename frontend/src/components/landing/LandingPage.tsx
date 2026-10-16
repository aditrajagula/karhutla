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
          Apa itu JagaBorneo? Platform geospasial terpadu untuk pemantauan kebakaran hutan dan
          lahan (karhutla) serta deforestasi di Pulau Kalimantan secara real-time. JagaBorneo
          mengintegrasikan deteksi anomali termal satelit NASA FIRMS, analisis kehilangan tutupan
          pohon, peta kawasan hutan dan kesatuan hidrologis gambut, serta estimasi risiko berbasis
          cuaca untuk mendukung pemantauan dini dan pelaporan lingkungan yang akurat.
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
