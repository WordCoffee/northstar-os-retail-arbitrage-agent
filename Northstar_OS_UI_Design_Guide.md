# NORTH STAR OS — UI DESIGN GUIDE
**Version:** 1.0  
**Date:** September 8, 2026  
**Purpose:** Frontend development reference for the North Star OS website.

---

## 1. DESIGN A: "THE ANALYST’S DESK"
**Philosophy:** High-end physical workspace meets digital precision. A "Craftsman" aesthetic that feels premium, tactile, and professional.

### 1.1 Visual Identity
*   **Theme:** Neo-Skeuomorphic (Physical textures + Digital glow).
*   **Background:** Dark slate or charcoal texture (feels like a high-end desk pad or leather).
*   **Primary Panels:** "Physical" materials like brushed aluminum (sidebar) and digital "leather" (main card borders).
*   **Color Palette:** 
    *   **Profit/Success:** Amber / Gold (#D4AF37).
    *   **Navigation/Primary:** Steel Blue (#4682B4).
    *   **Critical Alerts:** Deep Crimson / "Red Wax" (#8B0000).
    *   **Background:** Charcoal (#1A1A1A).
*   **Typography:** 
    *   **Headers:** *Playfair Display* or *Merriweather* (Premium, elegant).
    *   **Data/Body:** *Roboto Mono* or *IBM Plex Mono* (Clean, technical).

### 1.2 Layout Architecture
*   **Top Navigation (The "Ribbon"):** 
    *   Gold-accented bar.
    *   **Global Stats:** Total Profit, BSR Health.
    *   **Global Search:** Styled like a physical magnifying glass with a glowing rim.
*   **Left Sidebar (The "Drawer"):** 
    *   A vertical list of "Notebooks" (Research, Inventory, SEO, Profit).
    *   **Interaction:** When active, the notebook "opens" (visual slide) onto the main screen.
*   **Main Center (The "Work Surface"):** 
    *   High-density data tables.
    *   **Card System:** Each row is a "Physical Card" with a subtle drop shadow and "paper" texture.
    *   **Pinning:** Users can drag and "pin" cards to the right sidebar.
*   **Right Sidebar (The "Bulletin Board"):** 
    *   A digital corkboard where you pin "Actionable Notes" (e.g., "Price war on B08X," "Stock out in 5 days").

### 1.3 Interaction: The Paperclip Assistant
*   **Visual:** A 3D "Paperclip" character (reminiscent of Clippy but modern and sleek) sits on the edge of the screen.
*   **Trigger:** When a "Profit Spike" or "Rank Drop" occurs, the paperclip "holds up" a tiny digital note with the insight.

### 1.4 Components
*   **Knobs/Sliders:** High-end metal-looking rotary knobs for adjusting "Profit Targets" or "Inventory Levels."
*   **Data Tables:** Rows look like index cards.
*   **Charts:** Line charts that look like "ink plots" on graph paper.

---

## 2. DESIGN B: "THE LIVING DASHBOARD"
**Philosophy:** Data feels like a fluid, living ecosystem. Airy, modern, and high-energy.

### 2.1 Visual Identity
*   **Theme:** Glassmorphism (Frosted glass + Vibrant gradients).
*   **Background:** Deep navy gradient (#0a0e27 to #1a1a2e).
*   **Primary Panels:** Semi-transparent "Frosted Glass" with a subtle white border (backdrop-filter: blur).
*   **Color Palette:** 
    *   **Active/Primary:** Electric Cyan (#00f0ff).
    *   **Profit/Success:** Neon Lime (#39ff14).
    *   **AI Features:** Soft Purple (#a855f7).
    *   **Text:** Pure White (#FFFFFF) and Soft Gray (#94A3B8).
*   **Typography:** 
    *   **Headers:** *Exo 2* (Futuristic, sharp).
    *   **Body:** *Inter* (Clean, modern, highly readable).

### 2.2 Layout Architecture
*   **Center Metric (The "Heartbeat"):** 
    *   A large, glowing profit number in the center-top that "breathes" (pulses slightly) with every sale.
*   **Floating Bubbles (KPIs):** 
    *   Key stats (Sales, Units, Reviews, Revenue) are represented as semi-transparent bubbles of different sizes.
    *   **Interaction:** Hovering over a bubble expands it to reveal a "Liquid Chart" (a chart that looks like swirling water).
*   **Action Dock (The "Space Bar"):** 
    *   A floating glass dock at the bottom of the screen for quick navigation (Research, Profit, Alerts, Settings).
    *   Icons glow Cyan when active.
*   **The "Opportunity Map" Toggle:** 
    *   A button that "explodes" the standard table view into a **3D Topographical Map** of the market (mountains = competition, valleys = opportunity).

### 2.3 Interaction: The Liquid Chart
*   **Visual:** Charts are not static lines; they are "fluid" gradients that move slowly.
*   **Interaction:** Clicking a data point creates a "Ripple" effect across the chart.

### 2.4 Components
*   **Buttons:** "Pill-shaped" with a glowing border and a "click" ripple effect.
*   **Cards:** Glassmorphism cards with a "shimmer" effect on the border when hovered.
*   **Alerts:** Slide in from the right as glowing "Pills" of color (Red for danger, Green for success).

---

## 3. UNIVERSAL BRAND ELEMENTS (NORTH STAR)

### 3.1 Logo
*   **Name:** North Star.
*   **Icon:** A stylized, glowing 8-pointed star with a hollow center.
*   **Animation:** The star rotates slowly and "pulses" with a soft blue glow.

### 3.2 The "Polaris" Icon System
*   **Style:** Minimalist, 2px stroke, glowing edges when active.
*   **Specific Icons:**
    *   **The Compass:** For "Niche Finder."
    *   **The Crosshair:** For "Target ASIN."
    *   **The Battery:** For "Inventory Levels."
    *   **The Lightning Bolt:** For "Auto-Repricing."
    *   **The Prism:** For "Profit & Revenue."

### 3.3 Color Codes (Hex)
*   **Primary Blue:** #007bff
*   **Success Green:** #00ff9d
*   **Warning Amber:** #D4AF37
*   **Danger Red:** #ff00ff
*   **Background Dark:** #050505
