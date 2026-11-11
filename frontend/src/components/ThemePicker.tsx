import { useCallback, useEffect, useRef } from 'react'
import { canHover, useHoverOpen } from '../hooks/useHoverOpen'
import { paintTheme, THEMES, type ThemeId } from '../lib/themes'

type Props = {
  theme: ThemeId
  onChange: (theme: ThemeId) => void
}

// "themes ▾": hover (or tap) to see every theme. Hovering one previews it on
// the whole page; clicking keeps it; moving away puts yours back.
export default function ThemePicker({ theme, onChange }: Props) {
  const { open, setOpen, hover } = useHoverOpen()
  const root = useRef<HTMLDivElement>(null)
  const focusOnOpen = useRef(false)

  const restore = useCallback(() => paintTheme(theme), [theme])

  useEffect(() => {
    if (!open) restore()
  }, [open, restore])

  useEffect(() => {
    if (!open) return
    const options = () => [
      ...(root.current?.querySelectorAll<HTMLButtonElement>('.theme-option') ?? []),
    ]

    if (focusOnOpen.current) {
      focusOnOpen.current = false
      options()
        .find((o) => o.getAttribute('aria-checked') === 'true')
        ?.focus()
    }

    function onPointerDown(event: PointerEvent) {
      if (!root.current?.contains(event.target as Node)) setOpen(false)
    }
    // Capture phase: runs before the game's own shortcuts, so keys pressed in
    // this menu never answer a question or start a mode behind it.
    function onKey(event: KeyboardEvent) {
      if (event.key === 'Tab') return
      event.stopPropagation()
      if (event.key === 'Escape') {
        setOpen(false)
        root.current?.querySelector<HTMLButtonElement>('.theme-trigger')?.focus()
      } else if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
        event.preventDefault()
        const list = options()
        const index = list.indexOf(document.activeElement as HTMLButtonElement)
        const step = event.key === 'ArrowDown' ? 1 : -1
        const next =
          index < 0 ? (step > 0 ? 0 : list.length - 1) : (index + step + list.length) % list.length
        list[next]?.focus()
      }
    }
    document.addEventListener('pointerdown', onPointerDown)
    window.addEventListener('keydown', onKey, true)
    return () => {
      document.removeEventListener('pointerdown', onPointerDown)
      window.removeEventListener('keydown', onKey, true)
    }
  }, [open, setOpen])

  const current = THEMES.find((t) => t.id === theme) ?? THEMES[0]

  return (
    <div className="theme-picker" ref={root} {...hover}>
      <button
        className="theme-trigger"
        aria-haspopup="menu"
        aria-expanded={open}
        onClick={(event) => {
          // detail is 0 when the "click" came from the keyboard.
          focusOnOpen.current = event.detail === 0
          setOpen(canHover() && event.detail !== 0 ? true : !open)
        }}
      >
        <span className="theme-trigger-dot" style={{ background: current.swatch.accent }} />
        themes
        <span className="chevron" aria-hidden="true">
          ▾
        </span>
      </button>

      <div className={`theme-menu ${open ? 'open' : ''}`} role="menu" onMouseLeave={restore}>
        {THEMES.map((t) => (
          <button
            key={t.id}
            role="menuitemradio"
            aria-checked={t.id === theme}
            tabIndex={open ? 0 : -1}
            className={`theme-option ${t.id === theme ? 'active' : ''}`}
            onMouseEnter={() => paintTheme(t.id)}
            onFocus={() => paintTheme(t.id)}
            onClick={() => {
              onChange(t.id)
              setOpen(false)
            }}
          >
            <span className="theme-swatch" style={{ background: t.swatch.bg }} aria-hidden="true">
              <span style={{ color: t.swatch.text }}>Aa</span>
              <span className="theme-swatch-dot" style={{ background: t.swatch.accent }} />
            </span>
            <span className="theme-name">{t.name}</span>
            <span className="theme-vibe">{t.vibe}</span>
          </button>
        ))}
      </div>
    </div>
  )
}