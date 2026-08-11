export async function onRequestGet(context) {
  const { params, env } = context;
  const fileName = params.filename;

  if (!fileName || !fileName.endsWith(".json")) {
    return new Response(JSON.stringify({ error: "Invalid file name" }), {
      status: 400,
      headers: { "Content-Type": "application/json" }
    });
  }

  try {
    const raw = await env.DEALS_KV.get(`scored:${fileName}`);
    if (!raw) {
      return new Response(JSON.stringify({ error: "File not found" }), {
        status: 404,
        headers: { "Content-Type": "application/json" }
      });
    }
    return new Response(raw, { headers: { "Content-Type": "application/json" } });
  } catch (e) {
    return new Response(JSON.stringify({ error: e.message }), {
      status: 500,
      headers: { "Content-Type": "application/json" }
    });
  }
}
