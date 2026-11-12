import type { CSSProperties } from 'react'

// The moving scenery behind animated themes. Every scene is always in the page
// but hidden unless its theme is active (see index.css), so hovering a theme in
// the picker previews its scenery too. fx off freezes all of it.

// Pseudo-random but stable numbers (the same every render), so particles
// don't jump around when React re-renders.
function rand(i: number, salt: number): number {
  const x = Math.sin(i * 12.9898 + salt * 78.233) * 43758.5453
  return x - Math.floor(x)
}

type Range = [number, number]

function between([min, max]: Range, t: number): number {
  return min + (max - min) * t
}

type ParticlesProps = {
  kind: string
  count: number
  seconds: Range // how long one trip across the screen takes
  size: Range // px
  sway?: Range // px of side-to-side drift
}

function Particles({ kind, count, seconds, size, sway = [0, 0] }: ParticlesProps) {
  return Array.from({ length: count }, (_, i) => {
    const duration = between(seconds, rand(i, 1))
    const style = {
      '--x': `${rand(i, 2) * 100}%`,
      '--y': `${rand(i, 3) * 100}%`,
      '--d': `${duration.toFixed(2)}s`,
      '--delay': `${(-rand(i, 4) * duration).toFixed(2)}s`, // start mid-trip, so the scene is full at once
      '--s': `${between(size, rand(i, 5)).toFixed(1)}px`,
      '--sway': `${between(sway, rand(i, 6)).toFixed(0)}px`,
    } as CSSProperties
    return (
      <span key={i} className={`p ${kind}`} style={style}>
        <span />
      </span>
    )
  })
}

export default function Scenery() {
  return (
    <div className="backdrop" aria-hidden="true">
      <div className="scene scene-sunset">
        <span className="sun" />
        <Particles kind="cloud" count={5} seconds={[90, 160]} size={[180, 340]} />
        <span className="ridge far" />
        <span className="ridge near" />
      </div>

      <div className="scene scene-aurora">
        <Particles kind="star" count={45} seconds={[2, 6]} size={[1, 2.6]} />
        <span className="ribbon r1" />
        <span className="ribbon r2" />
        <span className="ribbon r3" />
      </div>

      <div className="scene scene-lofi">
        <span className="lamp" />
        <Particles kind="rain" count={70} seconds={[0.55, 0.95]} size={[12, 26]} />
        <Particles kind="trickle" count={8} seconds={[7, 14]} size={[3, 6]} />
      </div>

      <div className="scene scene-sakura">
        <Particles kind="petal" count={24} seconds={[10, 18]} size={[10, 16]} sway={[25, 70]} />
      </div>

      <div className="scene scene-deepsea">
        <span className="beam b1" />
        <span className="beam b2" />
        <span className="beam b3" />
        <span className="beam b4" />
        <Particles kind="bubble" count={24} seconds={[9, 18]} size={[3, 9]} sway={[4, 14]} />
      </div>
    </div>
  )
}