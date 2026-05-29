export function guestSessionId() {
  const key = "cf_guest_session";
  const existing = localStorage.getItem(key);
  if (existing) return existing;
  const next = crypto.randomUUID ? crypto.randomUUID() : `${Date.now()}-${Math.random().toString(16).slice(2)}`;
  localStorage.setItem(key, next);
  return next;
}

export function trackUsage(eventType: string, path = "/", meta: Record<string, unknown> = {}) {
  try {
    fetch("/api/usage/track", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        event_type: eventType,
        path,
        session_id: guestSessionId(),
        meta,
      }),
      keepalive: true,
    }).catch(() => {});
  } catch {
    /* never block UI */
  }
}
