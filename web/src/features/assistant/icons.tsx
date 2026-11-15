// Outline icons on the 24px grid, 2px stroke, like the admin nav (paths from Lucide, ISC licence).
const PATHS = {
  up: ['M7 10v12', 'M15 5.88 14 10h5.83a2 2 0 0 1 1.92 2.56l-2.33 8A2 2 0 0 1 17.5 22H4a2 2 0 0 1-2-2v-8a2 2 0 0 1 2-2h2.76a2 2 0 0 0 1.79-1.11L12 2a3.13 3.13 0 0 1 3 3.88Z'],
  down: ['M17 14V2', 'M9 18.12 10 14H4.17a2 2 0 0 1-1.92-2.56l2.33-8A2 2 0 0 1 6.5 2H20a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2h-2.76a2 2 0 0 0-1.79 1.11L12 22a3.13 3.13 0 0 1-3-3.88Z'],
  pencil: ['M21.174 6.812a1 1 0 0 0-3.986-3.987L3.842 16.174a2 2 0 0 0-.5.83l-1.321 4.352a.5.5 0 0 0 .623.622l4.353-1.32a2 2 0 0 0 .83-.497z', 'm15 5 4 4'],
  x: ['M18 6 6 18', 'm6 6 12 12'],
  ask: ['M7.9 20A9 9 0 1 0 4 16.1L2 22Z', 'M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3', 'M12 17h.01'],
} as const;

export function Icon({ name, className = 'size-4' }: { name: keyof typeof PATHS; className?: string }) {
  return (
    <svg viewBox="0 0 24 24" className={`${className} shrink-0 fill-none stroke-current stroke-2`} strokeLinecap="round" strokeLinejoin="round" aria-hidden>
      {PATHS[name].map((d) => <path key={d} d={d} />)}
    </svg>
  );
}

/** The site's focus ring, for small controls that don't use btn. */
export const focus = 'outline-offset-2 focus-visible:outline-2 focus-visible:outline-leaf-700';
