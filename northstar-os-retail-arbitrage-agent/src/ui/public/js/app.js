async function loadDeals() {
  const res = await fetch('/api/deals');
  const deals = await res.json();
  const tbody = document.getElementById('deals-body');
  tbody.innerHTML = deals.map(d => `
    <tr>
      <td>${d.title ?? ''}</td>
      <td>$${d.price ?? ''}</td>
      <td>${d.marginPercent ?? ''}%</td>
      <td>${d.roiPercent ?? ''}%</td>
      <td>${d.rating ?? ''}</td>
      <td><a href="${d.url}" target="_blank" rel="noopener">View</a></td>
    </tr>
  `).join('');
}
loadDeals();
