/**
 * Logs and (optionally) forwards top deals to a webhook (Slack/Discord).
 * Set WEBHOOK_URL in .env to enable forwarding.
 */
export async function alertTopDeals(deals, limit = 5) {
  const top = deals.slice(0, limit);

  console.log(`\nTop ${top.length} deal(s):`);
  top.forEach((d, i) => {
    console.log(
      `${i + 1}. ${d.title?.slice(0, 60)} | price $${d.price} | margin ${d.marginPercent}% | ROI ${d.roiPercent}%`
    );
  });

  const webhookUrl = process.env.WEBHOOK_URL;
  if (!webhookUrl) return;

  const axios = (await import('axios')).default;
  await axios.post(webhookUrl, {
    text: top.map(d => `${d.title} — $${d.price} — ROI ${d.roiPercent}%`).join('\n'),
  });
}
