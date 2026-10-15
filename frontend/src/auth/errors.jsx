// Turns an axios error from the auth endpoints into a short message for the UI.
export function formatAuthError(error) {
  if (!error.response) {
    return 'Cannot reach the server. If it was idle it can take up to a minute to wake up - please try again.'
  }
  const detail = error.response.data?.detail
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail) && detail.length > 0) {
    // 422 validation errors: show the first one, e.g. "String should have at least 8 characters"
    return detail[0].msg || 'Please check the form and try again.'
  }
  if (error.response.status === 429) return 'Too many attempts. Please wait a minute and try again.'
  return 'Something went wrong. Please try again.'
}
