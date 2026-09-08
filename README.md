# AutoTactix — Frontend

Production-ready frontend for the AutoTactix landing page, built with React,
TypeScript, Vite, Tailwind CSS, and Lucide icons.

## Getting started

```bash
npm install
npm run dev
```

Then open the printed local URL (usually `http://localhost:5173`).

To create a production build:

```bash
npm run build
npm run preview
```

## Environment variables

Copy `.env.example` to `.env` and set `VITE_API_BASE_URL` once a real
AutoTactix backend endpoint exists. Until then, the contact form runs in a
self-contained mode: it validates the input and simulates a network
round trip so every UI state (sending, success, error) can be exercised.

```bash
cp .env.example .env
```

## Project structure

```
src/
├── assets/
│   ├── hero/traffic-city.svg   # isometric smart-city illustration
│   └── logo/autotactix-logo.svg
├── components/                 # Navbar, Hero, FeatureSection, etc.
├── data/                       # features.ts, faq.ts (content, separated from UI)
├── services/contactService.ts  # abstraction layer for the contact form
├── hooks/useTheme.ts           # light/dark theme with localStorage persistence
├── types/index.ts
├── App.tsx
├── main.tsx
└── index.css                   # CSS variable design tokens (light + dark)
```

## Notes on the hero illustration

The brief asks for a local asset rather than an external stock image. Since a
crisp raster illustration wasn't available to source locally without using
copyrighted stock photography, the hero visual was rebuilt as a local SVG
(`src/assets/hero/traffic-city.svg`) that reproduces the same visual
structure as the approved design: an isometric intersection, a bus, cars,
trees, and low-rise buildings. It's used exactly like a static image asset
(`<img src={...} />`) and can be swapped for a licensed raster asset later
without touching any component logic.

## Design system

Colors, spacing, and typography follow the approved screenshot exactly. All
themeable values are defined as CSS variables in `src/index.css`:

`--background`, `--foreground`, `--primary`, `--primary-foreground`,
`--muted`, `--muted-foreground`, `--border`, `--card`, `--accent`,
`--accent-soft`

Dark mode redefines the same variables rather than introducing a second
layout, so the visual hierarchy from the light-mode design carries over
unchanged.

## Accessibility

- Semantic landmarks (`header`, `nav`, `main`, `section`, `footer`).
- All interactive elements are real `<button>`s with visible focus rings.
- The FAQ accordion uses `aria-expanded` / `aria-controls`, is keyboard
  operable, and only one item is open at a time.
- The contact textarea has an associated (visually hidden) label, and
  validation/status messages are announced via `aria-live="polite"`.
- Animations respect `prefers-reduced-motion`.

## What was intentionally left out

Per the brief, this is a frontend-only deliverable: no AI/ML model, no
simulation engine, no backend, no database, and no authentication are
implemented. `contactService.ts` is structured so a real backend can be
wired in later by setting `VITE_API_BASE_URL`.
