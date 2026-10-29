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

// Every request carries the player's sign-in token so the backend knows who they are.
async function post<T>(path: string, body?: unknown): Promise<T> {
  const { data } = await supabase.auth.getSession()
  const token = data.session?.access_token

  const response = await fetch(`${API_URL}${path}`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: body === undefined ? undefined : JSON.stringify(body),
  })

  if (!response.ok) {
    throw new Error(`API error ${response.status}: ${await response.text()}`)
  }
  return response.json() as Promise<T>
}

export const api = {
  nextQuestion: () => post<NextQuestion>('/solo/next'),
  submitAnswer: (attemptId: string, choice: number | null) =>
    post<AnswerResult>('/solo/answer', { attempt_id: attemptId, choice }),
}