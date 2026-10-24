export async function api(path: string, body?: unknown, method = "POST") {
  const response = await fetch("/api" + path, {
    method: body === undefined ? "GET" : method,
    credentials: "same-origin",
    headers: {
      "Content-Type": "application/json",
      "X-ZeroWall-Director": "1",
      "Idempotency-Key": crypto.randomUUID(),
    },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  const value = await response
    .json()
    .catch(() => ({ detail: "The server returned an unreadable response." }));
  if (!response.ok)
    throw new Error(
      typeof value.detail === "string"
        ? value.detail
        : JSON.stringify(value.detail),
    );
  return value;
}

export class HostedAccessRequired extends Error {}

export async function openLocalSession() {
  const token = new URLSearchParams(location.hash.slice(1)).get("director");
  if (token) {
    history.replaceState(null, "", location.pathname + location.search);
    await api("/session", { token });
  } else {
    const session = await api("/session");
    if (session.authenticated) return;
    if (!session.local_entry)
      throw new HostedAccessRequired("Enter the access code for this council.");
    await api("/session/local", {});
  }
}
