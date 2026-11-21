/** Small drawn icons in the tab bar's line style (2px stroke, round ends).
 * Drawn, never Unicode characters: those render differently on every phone
 * and font, and read as placeholders. Decorative: always aria-hidden. */

type Direction = 'left' | 'right' | 'down' | 'up'

const CHEVRON: Record<Direction, string> = {
  left: 'M15 6l-6 6 6 6',
  right: 'M9 6l6 6-6 6',
  down: 'M6 9l6 6 6-6',
  up: 'M6 15l6-6 6 6',
}

export function Chevron({ direction, size = 18 }: { direction: Direction; size?: number }) {
  return (
    <svg className="icon" width={size} height={size} viewBox="0 0 24 24" aria-hidden="true">
      <path d={CHEVRON[direction]} />
    </svg>
  )
}

/** A filled triangle for a change: up or down. Colour comes from the parent
 * (good or bad), the words beside it say "up" / "down" for screen readers. */
export function ChangeArrow({ up }: { up: boolean }) {
  return (
    <svg className="icon icon-fill" width={10} height={10} viewBox="0 0 10 10" aria-hidden="true">
      <path d={up ? 'M5 1l4.5 7.5h-9z' : 'M5 9L.5 1.5h9z'} />
    </svg>
  )
}

/** Two arrows: tap to switch (the currency on a card). */
export function Swap({ size = 14 }: { size?: number }) {
  return (
    <svg className="icon" width={size} height={size} viewBox="0 0 24 24" aria-hidden="true">
      <path d="M7 4L3 8l4 4M3 8h14M17 12l4 4-4 4M21 16H7" />
    </svg>
  )
}
