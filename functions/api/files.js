export async function onRequestGet(context) {
  const { env } = context;
  try {
    const raw = await env.DEALS_KV.get("scored:index");
    return new Response(raw || "[]", {
      headers: { "Content-Type": "application/json" }
    });
  } catch (e) {
    return new Response(JSON.stringify({ error: e.message }), {
      status: 500,
      headers: { "Content-Type": "application/json" }
    });
  }
}
