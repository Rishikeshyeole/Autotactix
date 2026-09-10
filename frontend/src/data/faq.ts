import type { FAQ } from '../types';

export const faqs: FAQ[] = [
  {
    id: 'what-does-autotactix-do',
    question: 'What exactly does AutoTactix do?',
    answer:
      'AutoTactix analyzes traffic and road conditions, identifies congestion causes, generates multiple possible interventions, and evaluates them through simulation before recommending practical solutions.',
  },
  {
    id: 'what-data-required',
    question: 'What data does AutoTactix require?',
    answer:
      'AutoTactix works with traffic volume counts, road network layouts, signal timing data, and camera or sensor feeds where available. It is designed to produce useful insights even when only partial data is provided.',
  },
  {
    id: 'existing-infrastructure',
    question: 'Can it work with existing infrastructure?',
    answer:
      'Yes. AutoTactix is built to analyze and optimize the infrastructure a city already has, including existing signals, junctions, and road layouts, before recommending any new construction.',
  },
  {
    id: 'how-simulation-works',
    question: 'How does the simulation work?',
    answer:
      'Proposed interventions are modeled in a virtual traffic environment that reflects real intersection geometry and traffic flow, allowing outcomes to be tested safely before any real-world changes are made.',
  },
  {
    id: 'how-best-solution-selected',
    question: 'How does AutoTactix select the best solution?',
    answer:
      'Each simulated solution is scored against metrics such as congestion reduction, travel time, and implementation cost, and the options are ranked so planners can choose the best fit for their constraints.',
  },
  {
    id: 'who-can-use',
    question: 'Who can use AutoTactix?',
    answer:
      'AutoTactix is designed for urban planners, municipal traffic authorities, transportation engineers, and researchers working on improving road networks and reducing congestion in Indian cities.',
  },
];
