import { useEffect, useRef, useState } from 'react'
import type { PointerEvent as ReactPointerEvent } from 'react'

import type { AskChat as Chat } from '../useAskChat'
import { AskChat } from './AskChat'

// How far the window must be dragged down before letting go closes it.
const SWIPE_CLOSE_PX = 80

/** The round message button, bottom-right, and the chat window it opens. */
export function ChatBubble({ chat }: { chat: Chat }) {
  const [open, setOpen] = useState(false)
  const [drag, setDrag] = useState(0) // px the window is pulled down right now
  const dragStart = useRef<number | null>(null)
  const bubble = useRef<HTMLButtonElement>(null)

  // "Answer ready" dot: answers that finished while the window was closed.
  const finished = chat.turns.filter((t) => t.status !== 'waiting').length
  const [seen, setSeen] = useState(finished)
  if (open && seen !== finished) setSeen(finished) // open: everything is seen
  const unread = !open && finished > seen

  function close() {
    setOpen(false)
    setDrag(0)
    bubble.current?.focus() // back to where you were
  }

  // Esc closes it, like any pop-up.
  useEffect(() => {
    if (!open) return
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && close()
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [open])

  // Swipe down on the grab handle: follow the finger, close past the threshold.
  function onPointerDown(e: ReactPointerEvent<HTMLDivElement>) {
    dragStart.current = e.clientY
    e.currentTarget.setPointerCapture(e.pointerId)
  }
  function onPointerMove(e: ReactPointerEvent<HTMLDivElement>) {
    if (dragStart.current === null) return
    setDrag(Math.max(0, e.clientY - dragStart.current))
  }
  function onPointerUp() {
    if (dragStart.current === null) return
    dragStart.current = null
    if (drag > SWIPE_CLOSE_PX) close()
    else setDrag(0) // not far enough: spring back
  }

  return (
    <>
      {open && (
        <div
          className="chat-window"
          role="dialog"
          aria-label="Ask about your spending"
          style={drag ? { transform: `translateY(${drag}px)`, transition: 'none' } : undefined}
        >
          <div
            className="chat-window-top"
            onPointerDown={onPointerDown}
            onPointerMove={onPointerMove}
            onPointerUp={onPointerUp}
            onPointerCancel={onPointerUp}
          >
            <span className="grab-handle" aria-hidden="true" />
            <button type="button" className="chat-close" aria-label="Close chat" onClick={close}>
              <svg viewBox="0 0 24 24" aria-hidden="true">
                <path d="M6 6l12 12M18 6L6 18" />
              </svg>
            </button>
          </div>
          <AskChat chat={chat} autoFocus />
        </div>
      )}
      <button
        ref={bubble}
        type="button"
        className="chat-bubble"
        aria-label={unread ? 'Ask about your spending (new answer)' : 'Ask about your spending'}
        aria-expanded={open}
        onClick={() => (open ? close() : setOpen(true))}
      >
        <svg viewBox="0 0 24 24" aria-hidden="true">
          <path d="M4 5h16v11H9l-5 4z" />
        </svg>
        {unread && <span className="chat-dot" aria-hidden="true" />}
      </button>
    </>
  )
}
