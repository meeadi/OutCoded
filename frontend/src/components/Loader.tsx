import { useState } from 'react'
import TypedLogo from './TypedLogo'

// OutCoded's loading animation everywhere: "outcoded" typing itself on repeat.
// It fades in after a beat, so quick loads never flash it.
export default function Loader({ label }: { label?: string }) {
  // Read the fx setting once (it lives on <html>), so this works anywhere.
  const [animate] = useState(() => document.documentElement.dataset.fx !== 'off')
  return (
    <div className="loader" role="status">
      <TypedLogo animate={animate} loop className="loader-logo" />
      {label && <p className="loader-label">{label}</p>}
    </div>
  )
}