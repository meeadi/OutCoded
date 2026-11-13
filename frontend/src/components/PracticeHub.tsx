import { useCallback, useEffect, useState } from 'react'
import { api, type PracticeTopics } from '../lib/api'
import {
  loadSettings,
  MODES,
  PRESETS,
  saveSettings,
  type PracticeSettings,
  type Preset,
} from '../lib/practice'
import Loader from './Loader'

type Props = {
  onStart: (settings: PracticeSettings) => void
  onBack: () => void
}

// Pick topics, a difficulty and a mode. Enter starts with whatever's selected,
// and the choices are remembered, so "1, Enter" from the menu is a quick rush.
export default function PracticeHub({ onStart, onBack }: Props) {
  const [settings, setSettings] = useState<PracticeSettings>(loadSettings)
  const [data, setData] = useState<PracticeTopics | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    api
      .practiceTopics()
      .then((d) => !cancelled && setData(d))
      .catch((e) => !cancelled && setError(e instanceof Error ? e.message : String(e)))
    return () => {
      cancelled = true
    }
  }, [])

  const update = useCallback((change: Partial<PracticeSettings>) => {
    setSettings((previous) => {
      const next = { ...previous, ...change }
      saveSettings(next)
      return next
    })
  }, [])

  const review = settings.variant === 'review'
  // How many questions a topic offers right now: mistakes in review, else the preset's count.
  const countFor = useCallback(
    (topic: PracticeTopics['topics'][number]) =>
      review ? topic.mistakes : topic.counts[settings.preset],
    [review, settings.preset],
  )

  const known = new Set(data?.topics.map((t) => t.id) ?? [])
  const selected = settings.topics.filter((id) => known.has(id))
  const chosenTopics = data
    ? data.topics.filter((t) => selected.length === 0 || selected.includes(t.id))
    : []
  const available = chosenTopics.reduce((sum, t) => sum + countFor(t), 0)
  const anyAtAll = chosenTopics.reduce((sum, t) => sum + (review ? t.mistakes : t.counts.all), 0)
  const canStart = data !== null && anyAtAll > 0

  const start = useCallback(() => {
    if (canStart) onStart({ ...settings, topics: selected })
  }, [canStart, onStart, settings, selected])

  function toggleTopic(id: string) {
    const next = selected.includes(id) ? selected.filter((t) => t !== id) : [...selected, id]
    update({ topics: next })
  }

  // Keyboard: 1-5 pick a mode, Enter starts, Esc goes back.
  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      const n = Number(event.key)
      if (n >= 1 && n <= MODES.length) update({ variant: MODES[n - 1].id })
      else if (event.key === 'Enter') {
        event.preventDefault()
        start()
      } else if (event.key === 'Escape') onBack()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [update, start, onBack])

  if (error) {
    return (
      <div className="codeoff-center">
        <p className="auth-message">{error}</p>
        <button className="link" onClick={onBack}>
          ← back to menu
        </button>
      </div>
    )
  }
  if (!data) return <Loader />

  return (
    <div className="practice">
      <h2 className="auth-title">practice</h2>

      <section className="practice-section">
        <p className="practice-label">topics</p>
        <div className="chips">
          <button
            className={`chip ${selected.length === 0 ? 'on' : ''}`}
            onClick={() => update({ topics: [] })}
          >
            all
          </button>
          {data.topics.map((topic) => {
            const count = countFor(topic)
            const empty = (review ? topic.mistakes : topic.counts.all) === 0
            return (
              <button
                key={topic.id}
                className={`chip ${selected.includes(topic.id) ? 'on' : ''}`}
                onClick={() => toggleTopic(topic.id)}
                disabled={empty}
                title={
                  empty
                    ? review
                      ? 'no mistakes to review here'
                      : 'questions coming soon'
                    : undefined
                }
              >
                {topic.name}
                <span className="chip-count">{empty ? (review ? '0' : 'soon') : count}</span>
              </button>
            )
          })}
        </div>
      </section>

      {!review && (
        <section className="practice-section">
          <p className="practice-label">difficulty</p>
          <div className="segmented">
            {PRESETS.map((preset) => (
              <button
                key={preset.id}
                className={settings.preset === preset.id ? 'on' : ''}
                onClick={() => update({ preset: preset.id as Preset })}
              >
                <span className="segment-name">{preset.name}</span>
                <span className="segment-hint">{preset.hint}</span>
              </button>
            ))}
          </div>
        </section>
      )}

      <section className="practice-section">
        <p className="practice-label">mode</p>
        <div className="practice-modes">
          {MODES.map((mode, i) => (
            <button
              key={mode.id}
              className={`mode practice-mode ${settings.variant === mode.id ? 'on' : ''}`}
              onClick={() => update({ variant: mode.id })}
            >
              <span className="option-key">{i + 1}</span>
              <span className="mode-name">{mode.name}</span>
              <span className="mode-desc">{mode.desc}</span>
            </button>
          ))}
        </div>
      </section>

      <button className="btn-primary practice-start" onClick={start} disabled={!canStart}>
        {canStart ? `start ${settings.variant}` : review ? 'nothing to review' : 'no questions yet'}
      </button>
      <p className="practice-note">
        {!canStart
          ? review
            ? "you've fixed every mistake in these topics. nice."
            : 'these topics are still getting their questions.'
          : !review && available === 0
            ? "nothing at this difficulty yet: we'll mix in other levels."
            : `${available} question${available === 1 ? '' : 's'} ready · press enter · practice never touches your rating`}
      </p>
    </div>
  )
}