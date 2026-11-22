import type { Category } from './api/client'

// Colours live in index.css (--cat-1 ... --cat-8, --cat-neutral) with separate light and
// dark values, validated for colour-blind separation by the dataviz palette script.
// Only 8 colours pass, so two categories share the neutral grey: Health and Other, the
// ones used least. Bills (rent: usually the biggest slice) gets a real colour, or most of
// the ring would look like an empty track. The legend names every slice either way.
// The ORDER matters: neighbouring slots were validated as neighbours, so slices are
// drawn in this order, not in the API's alphabetical order.
export const CATEGORY_SLOT: Record<Category, string> = {
  Bills: 'var(--cat-1)',
  Food: 'var(--cat-2)',
  Groceries: 'var(--cat-3)',
  Travel: 'var(--cat-4)',
  Shopping: 'var(--cat-5)',
  Transport: 'var(--cat-6)',
  Subscriptions: 'var(--cat-7)',
  Entertainment: 'var(--cat-8)',
  Health: 'var(--cat-neutral)',
  Other: 'var(--cat-neutral)',
}
export const DRAW_ORDER = Object.keys(CATEGORY_SLOT) as Category[]
