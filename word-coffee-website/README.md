# Word Coffee Website

This is the static website for [word-coffee.com](https://word-coffee.com), hosted on GitHub Pages.

## Pages

| File | Description |
|------|-------------|
| `index.html` | Homepage |
| `about.html` | Our story & mission |
| `products.html` | Card deck collections |
| `informational.html` | Science behind the words |
| `learn-more.html` | Resources & guides |
| `northstar.html` | **Northstar OS overview page** (NEW) |
| `contact.html` | Contact form |

## Northstar OS Page

- **Route:** `/northstar.html` (or `/northstar` with GitHub Pages pretty URLs)
- **Purpose:** Public marketing/overview page for the Northstar OS retail arbitrage platform
- **Access:** This page is **publicly accessible**. The actual Northstar OS dashboard and API are protected by **Cloudflare Access** (Zero Trust) on the `/northstar` path of the deployment target.
- **No secrets exposed:** This page contains no API keys, internal endpoints, or sensitive configuration.

### Adding Cloudflare Access Protection (Production)

When deploying to a custom domain (e.g., `northstar.word-coffee.com` or path-based on main domain):

1. In Cloudflare Zero Trust → Access → Applications → Add Application
2. Select **Self-hosted**
3. Application domain: `yourdomain.com/northstar*` (path-based) or subdomain
4. Policy: Allow → Emails ending in `@yourdomain.com` (or GitHub/Google SSO)
4. Save — Cloudflare handles auth at the edge, no code changes needed

## Local Development

Just open any `.html` file in a browser. No build step required.

## Deployment

GitHub Pages auto-deploys from `main` branch. Push to `main` → live in ~1 minute.

```bash
git add .
git commit -m "Add Northstar OS landing page + nav updates"
git push origin main
```

## Styling

All styles in `style.css`. Uses CSS custom properties (implicit via repeated values), no preprocessor.

## License

© 2025 Word Coffee. A T2 Holdings LLC Brand.