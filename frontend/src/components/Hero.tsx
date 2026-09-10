import { ArrowRight, BarChart3, Leaf, MapPin } from 'lucide-react';
import type { ReactNode } from 'react';
import heroImage from '../assets/hero/traffic-city.svg';
import logo from '../assets/logo/autotactix-logo.svg';

export default function Hero() {
  const handleTryNow = () => {
    const novncUrl =
      import.meta.env.VITE_NOVNC_URL || 'http://161.118.190.216:6080/vnc.html';
    window.open(novncUrl, '_blank', 'noopener,noreferrer');
  };

  return (
    <section id="home" className="relative overflow-hidden">
      <div className="mx-auto grid max-w-7xl grid-cols-1 items-center gap-12 px-6 py-16 md:py-24 lg:grid-cols-2 lg:gap-8">
        <div>
          <h1
            className="text-4xl font-extrabold leading-tight tracking-tight sm:text-5xl"
            style={{ color: 'var(--foreground)' }}
          >
            We Don&rsquo;t Just
            <br />
            Analyze Traffic —
            <br />
            We Create{' '}
            <span style={{ color: 'var(--primary)' }}>Intelligent</span>
            <br />
            <span style={{ color: 'var(--primary)' }}>Solutions</span>.
          </h1>

          <p
            className="mt-6 max-w-md text-base leading-relaxed"
            style={{ color: 'var(--muted-foreground)' }}
          >
            AutoTactix analyzes congestion, uncovers its root causes, and
            simulates practical, India-ready solutions before they ever reach
            the road.
          </p>

          <button
            type="button"
            onClick={handleTryNow}
            className="focus-ring group mt-8 inline-flex items-center gap-2 rounded-full px-6 py-3 text-sm font-semibold text-white shadow-sm transition-all duration-200 ease-smooth hover:shadow-md active:scale-[0.97]"
            style={{ backgroundColor: 'var(--primary)' }}
            onMouseEnter={(e) =>
              (e.currentTarget.style.backgroundColor = 'var(--primary-hover)')
            }
            onMouseLeave={(e) =>
              (e.currentTarget.style.backgroundColor = 'var(--primary)')
            }
          >
            Try Now
            <ArrowRight
              size={16}
              className="transition-transform duration-200 group-hover:translate-x-0.5"
            />
          </button>
        </div>

        <div className="relative">
          <img
            src={heroImage}
            alt="Isometric illustration of a smart-city traffic intersection with a bus, cars, buildings and trees"
            className="w-full"
          />

          <FloatingLabel
            className="left-2 top-4 sm:left-6 sm:top-6"
            icon={<LogoBadge />}
            label="AI Analysis"
          />
          <FloatingLabel
            className="right-0 top-1/3 sm:right-2"
            icon={<BarChart3 size={16} style={{ color: 'var(--primary)' }} />}
            label="Simulation"
          />
          <FloatingLabel
            className="left-8 bottom-1/4 sm:left-16"
            icon={<MapPin size={16} style={{ color: 'var(--primary)' }} />}
            label="Better Solutions"
          />
          <FloatingLabel
            className="bottom-2 right-0 sm:bottom-4"
            icon={<Leaf size={16} style={{ color: 'var(--primary)' }} />}
            label={
              <>
                Smarter Cities
                <br />
                Brighter Tomorrows
              </>
            }
          />
        </div>
      </div>
    </section>
  );
}

function LogoBadge() {
  return <img src={logo} alt="" className="h-4 w-4" aria-hidden="true" />;
}

interface FloatingLabelProps {
  icon: ReactNode;
  label: ReactNode;
  className?: string;
}

function FloatingLabel({ icon, label, className = '' }: FloatingLabelProps) {
  return (
    <div
      className={`absolute flex items-center gap-2 rounded-xl border px-3 py-2 text-xs font-medium shadow-sm ${className}`}
      style={{
        backgroundColor: 'var(--card)',
        borderColor: 'var(--border)',
        color: 'var(--foreground)',
      }}
    >
      {icon}
      <span className="leading-tight">{label}</span>
    </div>
  );
}