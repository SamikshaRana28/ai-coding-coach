import { useEffect, useState } from 'react'
import { getSettings, updateSettings, errorMessage } from '../api'

export default function Settings() {
  const [settings, setSettings] = useState(null)
  const [error, setError] = useState(null)
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)

  useEffect(() => {
    let cancelled = false
    getSettings()
      .then((res) => { if (!cancelled) setSettings(res.data) })
      .catch((e) => { if (!cancelled) setError(errorMessage(e)) })
    return () => { cancelled = true }
  }, [])

  const toggle = async (e) => {
    const next = e.target.checked
    setSaving(true)
    setError(null)
    setSaved(false)
    try {
      const res = await updateSettings({ notify_email: next })
      setSettings(res.data)
      setSaved(true)
    } catch (err) {
      setError(errorMessage(err))
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="space-y-6 max-w-2xl">
      <h1 className="text-3xl font-bold">⚙️ Settings</h1>
      {error && <div role="alert" className="bg-red-50 border border-red-200 text-red-700 rounded-lg p-3 text-sm">{error}</div>}
      {!settings && !error && <p className="text-slate-400 animate-pulse">Loading…</p>}
      {settings && (
        <section className="bg-surface rounded-xl p-6 border border-slate-200 space-y-3">
          <h2 className="font-bold">Reminders</h2>
          <p className="text-sm text-slate-500">
            The Coach always shows reminders inside the app. You can also get a short email in the morning and a
            streak-save reminder in the evening when you still have tasks pending.
          </p>
          <label className="flex items-center gap-3 text-sm">
            <input
              type="checkbox"
              checked={settings.notify_email}
              disabled={saving}
              onChange={toggle}
              className="w-4 h-4"
            />
            Email me study reminders{settings.email ? ` at ${settings.email}` : ''}
          </label>
          {!settings.email_available && (
            <p className="text-xs text-amber-700 bg-amber-50 border border-amber-200 rounded-lg px-3 py-2">
              Email sending is not set up on the server yet, so you will only see in-app reminders for now. Your choice is saved.
            </p>
          )}
          {saved && <p className="text-xs text-green-700">Saved.</p>}
        </section>
      )}
    </div>
  )
}
