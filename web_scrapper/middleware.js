const RATE_LIMIT_WINDOW_MS = 60_000;
const MAX_REQUESTS_PER_WINDOW = 60;

const ipHits = new Map();

function cleanup() {
  const now = Date.now();
  for (const [ip, entry] of ipHits) {
    if (now - entry.windowStart > RATE_LIMIT_WINDOW_MS * 2) {
      ipHits.delete(ip);
    }
  }
}

export default function middleware(request) {
  const ip =
    request.headers.get("x-forwarded-for")?.split(",")[0]?.trim() ||
    request.headers.get("x-real-ip") ||
    "unknown";

  const now = Date.now();
  let entry = ipHits.get(ip);

  if (!entry || now - entry.windowStart > RATE_LIMIT_WINDOW_MS) {
    entry = { windowStart: now, count: 0 };
    ipHits.set(ip, entry);
  }

  entry.count++;

  if (ipHits.size > 10_000) cleanup();

  if (entry.count > MAX_REQUESTS_PER_WINDOW) {
    return new Response(JSON.stringify({ error: "Too many requests" }), {
      status: 429,
      headers: {
        "Content-Type": "application/json",
        "Retry-After": String(
          Math.ceil((entry.windowStart + RATE_LIMIT_WINDOW_MS - now) / 1000)
        ),
      },
    });
  }

  return undefined;
}

export const config = {
  matcher: ["/api/:path*"],
};
