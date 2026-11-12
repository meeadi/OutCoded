import { createClient } from '@supabase/supabase-js'

const url = import.meta.env.VITE_SUPABASE_URL
const key = import.meta.env.VITE_SUPABASE_PUBLISHABLE_KEY

if (!url || !key) {
  throw new Error('Missing VITE_SUPABASE_URL or VITE_SUPABASE_PUBLISHABLE_KEY in frontend/.env.local')
}

// Links in auth emails come back with details after the #. Read them before the
// client tidies the address bar.
const linkDetails = new URLSearchParams(window.location.hash.slice(1))

// Opened from a "reset your password" email?
export const arrivedFromRecoveryLink = linkDetails.get('type') === 'recovery'

// An expired or already-used email link comes back with an error instead of a session.
export const authLinkFailed = linkDetails.has('error_description')

export const supabase = createClient(url, key)