import { features } from '../data/features';
import FeatureCard from './FeatureCard';

export default function FeatureSection() {
  return (
    <section id="features" className="mx-auto max-w-7xl px-6 py-20">
      <div className="mx-auto max-w-2xl text-center">
        <p
          className="text-xs font-semibold tracking-wide"
          style={{ color: 'var(--primary)' }}
        >
          OUR FEATURES
        </p>
        <h2
          className="mt-3 text-3xl font-extrabold sm:text-4xl"
          style={{ color: 'var(--foreground)' }}
        >
          Powerful Features for
          <br />
          Real-World Impact
        </h2>
        <p
          className="mt-4 text-base leading-relaxed"
          style={{ color: 'var(--muted-foreground)' }}
        >
          From data to decisions — AutoTactix provides everything you need to
          understand, simulate, and solve urban traffic challenges.
        </p>
      </div>

      <div className="mt-12 grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-4">
        {features.map((feature) => (
          <FeatureCard key={feature.id} feature={feature} />
        ))}
      </div>
    </section>
  );
}
