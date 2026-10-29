import { supabase } from './supabase'

const API_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'

export type Question = {
  format: string
  category: string
  language: string | null
  difficulty: string
  prompt: string
  code: string | null
  options: string[]
  time_limit_s: number
}

export type NextQuestion = {
  attempt_id: string
  question: Question
}

export type AnswerResult = {
  correct: boolean
  timed_out: boolean
  correct_choice: number
  response_ms: number
  explanation: string
}

export type Profile = {
  id: string
  username: string | null
  rating: number
  rating_deviation: number
  created_at: string
}

// An error from our backend, carrying its HTTP status and readable message.
export class ApiError extends Error {
  status: number

  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

// Every request carries the player's sign-in token so the backend knows who they are.
async function request<T>(method: 'GET' | 'POST' | 'PUT', path: string, body?: unknown): Promise<T> {
  const { data } = await supabase.auth.getSession()
  const token = data.session?.access_token

  const response = await fetch(`${API_URL}${path}`, {
    method,
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: body === undefined ? undefined : JSON.stringify(body),
  })

  if (!response.ok) {
    let message = `Something went wrong (${response.status})`
    try {
      const error = await response.json()
      if (typeof error.detail === 'string') message = error.detail
    } catch {
      // response wasn't JSON; keep the generic message
    }
    throw new ApiError(response.status, message)
  }
  return response.json() as Promise<T>
}

export const api = {
  me: () => request<Profile>('GET', '/me'),
  setUsername: (username: string) => request<Profile>('PUT', '/me/username', { username }),
  nextQuestion: () => request<NextQuestion>('POST', '/solo/next'),
  submitAnswer: (attemptId: string, choice: number | null) =>
    request<AnswerResult>('POST', '/solo/answer', { attempt_id: attemptId, choice }),
}