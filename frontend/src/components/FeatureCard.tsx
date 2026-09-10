import type { Feature } from '../types';

interface FeatureCardProps {
  feature: Feature;
}

export default function FeatureCard({ feature }: FeatureCardProps) {
  const Icon = feature.icon;

  return (
    <div
      className="group rounded-2xl border p-6 transition-all duration-200 ease-smooth hover:-translate-y-1 hover:shadow-md"
      style={{ backgroundColor: 'var(--card)', borderColor: 'var(--border)' }}
    >
      <div
        className="mb-4 flex h-12 w-12 items-center justify-center rounded-xl transition-colors duration-200"
        style={{ backgroundColor: 'var(--accent-soft)' }}
      >
        <Icon size={22} style={{ color: 'var(--primary)' }} />
      </div>
      <h3
        className="mb-2 text-lg font-bold"
        style={{ color: 'var(--foreground)' }}
      >
        {feature.title}
      </h3>
      <p
        className="text-sm leading-relaxed"
        style={{ color: 'var(--muted-foreground)' }}
      >
        {feature.description}
      </p>
    </div>
  );
}
