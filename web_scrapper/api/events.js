const SUPABASE_URL = process.env.SUPABASE_URL;
const SUPABASE_KEY = process.env.SUPABASE_ANON_KEY;

const CORS_HEADERS = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Methods": "GET, OPTIONS",
  "Access-Control-Allow-Headers": "Content-Type",
};

const NO_STORE_HEADERS = {
  "Cache-Control": "no-store, no-cache, must-revalidate, proxy-revalidate",
  Pragma: "no-cache",
  Expires: "0",
  "Surrogate-Control": "no-store",
};

function applyHeaders(res, headers) {
  for (const [key, value] of Object.entries(headers)) {
    res.setHeader(key, value);
  }
}

export default async function handler(req, res) {
  if (req.method === "OPTIONS") {
    applyHeaders(res, CORS_HEADERS);
    applyHeaders(res, NO_STORE_HEADERS);
    return res.status(200).end();
  }

  if (req.method !== "GET") {
    applyHeaders(res, NO_STORE_HEADERS);
    return res.status(405).json({ error: "Method not allowed" });
  }

  if (!SUPABASE_URL || !SUPABASE_KEY) {
    applyHeaders(res, NO_STORE_HEADERS);
    return res.status(500).json({ error: "Server misconfigured" });
  }

  try {
    const { id } = req.query;

    let url;
    if (id) {
      const encoded = encodeURIComponent(id);
      url = `${SUPABASE_URL}/rest/v1/events?or=(link.eq.${encoded},id.eq.${encoded})&limit=1`;
    } else {
      url = `${SUPABASE_URL}/rest/v1/events?select=*`;
    }

    const response = await fetch(url, {
      headers: {
        apikey: SUPABASE_KEY,
        Authorization: `Bearer ${SUPABASE_KEY}`,
      },
    });

    if (!response.ok) {
      applyHeaders(res, NO_STORE_HEADERS);
      return res
        .status(response.status)
        .json({ error: "Upstream error", status: response.status });
    }

    const data = await response.json();

    applyHeaders(res, CORS_HEADERS);
    applyHeaders(res, NO_STORE_HEADERS);

    return res.status(200).json(data);
  } catch (err) {
    applyHeaders(res, NO_STORE_HEADERS);
    return res.status(502).json({ error: "Failed to fetch events" });
  }
}
