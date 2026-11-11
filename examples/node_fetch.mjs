// Example: any language works over HTTP. Node 18+.
const KALKAN = process.env.KALKAN_URL ?? "http://localhost:8088";

export async function isSafe(text) {
  try {
    const r = await fetch(`${KALKAN}/v1/check`, {
      method: "POST",
      headers: { "Content-Type": "application/json", Authorization: `Bearer ${process.env.KALKAN_KEY}` },
      body: JSON.stringify({ text, source: "user" }),
      signal: AbortSignal.timeout(2000),
    });
    if (!r.ok) return false;                 // fail closed
    return (await r.json()).decision !== "block";
  } catch {
    return false;                            // fail closed when Kalkan is unreachable
  }
}
