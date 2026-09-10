import { Brain, Settings2, BarChart3, Car } from 'lucide-react';
import type { Feature } from '../types';

export const features: Feature[] = [
  {
    id: 'ai-powered-analysis',
    title: 'AI-Powered Analysis',
    description:
      'Detects congestion patterns and identifies root causes using advanced AI models.',
    icon: Brain,
  },
  {
    id: 'multiple-solution-generation',
    title: 'Multiple Solution Generation',
    description:
      'Suggests alternative solutions from quick fixes to long-term infrastructure changes.',
    icon: Settings2,
  },
  {
    id: 'simulation-before-implementation',
    title: 'Simulation Before Implementation',
    description:
      'Tests and compares solutions in a virtual environment to ensure the best results.',
    icon: BarChart3,
  },
  {
    id: 'indian-driver-behavior-analysis',
    title: 'Indian Driver Behavior Analysis',
    description:
      'Analyzes real driving behavior patterns of Indian drivers to design practical, real-world solutions.',
    icon: Car,
  },
];
