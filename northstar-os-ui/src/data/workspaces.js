// The workspace specs, as data. GENERATED - do not hand-edit.
//
// Source of truth: ty/northstar_workspaces.json (scene_workspaces block).
// Regenerate with: node northstar-os-ui/scripts/sync-workspaces.mjs
//
// Emitted as a JS module rather than a .json file because this file is imported
// by src/lib/workspaceSpecs.js, which is unit-tested with `node --test`: Node's
// ESM loader refuses a bare JSON import without a `with { type: 'json' }`
// attribute, and Vite 5 rewrites the attribute away in some build paths. One
// plain module works in both.
//
// src/lib/workspaceSpecs.test.js fails when this object and the artifact
// disagree.

export const WORKSPACE_SPECS = {
  "schema": "northstar.scene_workspaces.v1",
  "mirrored_from": "ty/northstar_workspaces.json#scene_workspaces",
  "note": "The renderable copy of the scene_workspaces block. `src/lib/workspaceSpecs.test.js` fails when this file and ty/northstar_workspaces.json disagree, so the UI cannot drift into a second source of truth.",
  "core_six": [
    {
      "role": "design",
      "service": "design-studio"
    },
    {
      "role": "listings",
      "service": "listings"
    },
    {
      "role": "ppc",
      "service": "adpilot"
    },
    {
      "role": "golden-goose",
      "service": "golden-goose"
    },
    {
      "role": "research",
      "service": "product-finder"
    },
    {
      "role": "product-pictures",
      "service": "product-pictures"
    }
  ],
  "default_scene": {
    "service": "home",
    "label": "Deep Field",
    "variant": "orion-nursery",
    "why": "A service with no scene entry of its own (the catalogue rooms, admin, /home) renders the home field. The scene registry answers with this instead of null, so a new room can never paint nothing."
  },
  "default_workspace": {
    "id": "default",
    "label": "Workspace",
    "service": "",
    "core_role": "",
    "route": "",
    "scene": {
      "id": "home",
      "label": "Deep Field",
      "variant": "orion-nursery"
    },
    "views": {
      "param": "",
      "default": "workspace",
      "tabs_rendered_by": "page",
      "tabs": []
    },
    "bojo_tool": {
      "id": "",
      "status": "none",
      "owner": "",
      "source": "ty/bojo_tool_list.json",
      "note": "A non-core service opens no tool of its own; the frame stays off and the room keeps its page."
    },
    "gate": {
      "entitlement_key": "studio.",
      "decided_by": "northstar-os-ui/src/lib/serviceGate.js::canUseService",
      "dev": "dev_open",
      "denied": "no studio credit"
    },
    "why": "The fallback for every service that is not one of the core six: the home scene and no workspace frame, because the file only describes a workspace it can actually argue for."
  },
  "workspaces": [
    {
      "id": "design-studio",
      "click_path_view": "listing-images",
      "core_role": "design",
      "label": "Design Studio",
      "service": "design-studio",
      "route": "/design-studio",
      "page": "northstar-os-ui/src/pages/internal/DesignStudio.jsx",
      "page_title": "Design Studio",
      "page_anchor": "[data-testid=\"canvas-workspace\"]",
      "scene": {
        "id": "design-studio",
        "label": "Carina Ridge",
        "variant": "carina-cliffs"
      },
      "views": {
        "param": "section",
        "default": "canvas",
        "tabs_rendered_by": "page",
        "tabs": [
          {
            "id": "canvas",
            "label": "Canvas"
          },
          {
            "id": "projects",
            "label": "Projects"
          },
          {
            "id": "listing-images",
            "label": "Listing Images"
          },
          {
            "id": "aplus",
            "label": "A+ / Brand Story"
          },
          {
            "id": "storefront",
            "label": "Storefront"
          },
          {
            "id": "ads",
            "label": "Ads"
          },
          {
            "id": "video-ugc",
            "label": "Video & UGC Clips"
          },
          {
            "id": "social",
            "label": "Social"
          },
          {
            "id": "packaging",
            "label": "Packaging & Mockups"
          },
          {
            "id": "dielines",
            "label": "Dielines & Print"
          },
          {
            "id": "deliverables",
            "label": "Asset Dashboard"
          },
          {
            "id": "3d-scene",
            "label": "3D Product Scene"
          }
        ]
      },
      "bojo_tool": {
        "id": "generate_image",
        "status": "wired",
        "owner": "design-studio",
        "source": "ty/bojo_tool_list.json",
        "note": "chat_tools.TOOLS['generate_image'] renders one image locally and refuses to paint text, logos or barcodes."
      },
      "gate": {
        "entitlement_key": "studio.design-studio",
        "decided_by": "northstar-os-ui/src/lib/serviceGate.js::canUseService",
        "dev": "dev_open",
        "denied": "no studio credit"
      },
      "why": "Twelve sections of one creative job share a single canvas and one design document, so the workspace keeps them behind a section picker instead of pretending they are twelve separate rooms."
    },
    {
      "id": "listings",
      "click_path_view": "diffs",
      "core_role": "listings",
      "label": "Listing Guardian",
      "service": "listings",
      "route": "/listings",
      "page": "northstar-os-ui/src/pages/internal/ListingGuardian.jsx",
      "page_title": "Listing Guardian",
      "page_anchor": "nav[aria-label=\"Service navigation\"]",
      "scene": {
        "id": "listings",
        "label": "Globular Core",
        "variant": "globular-core"
      },
      "views": {
        "param": "view",
        "default": "alerts",
        "tabs_rendered_by": "page",
        "tabs": [
          {
            "id": "alerts",
            "label": "Alerts"
          },
          {
            "id": "diffs",
            "label": "Diffs"
          },
          {
            "id": "history",
            "label": "History"
          },
          {
            "id": "escalations",
            "label": "Escalations"
          }
        ]
      },
      "bojo_tool": {
        "id": "optimize_listing",
        "status": "wired",
        "owner": "listings",
        "source": "ty/bojo_tool_list.json",
        "note": "chat_tools.TOOLS['optimize_listing'] rewrites a listing from supplied facts."
      },
      "gate": {
        "entitlement_key": "studio.listings",
        "decided_by": "northstar-os-ui/src/lib/serviceGate.js::canUseService",
        "dev": "dev_open",
        "denied": "no studio credit"
      },
      "why": "A watchtower is read-first: alerts, then the diffs behind them, then what was done, then what was handed to a human - the tab order is the triage order."
    },
    {
      "id": "adpilot",
      "click_path_view": "terms",
      "core_role": "ppc",
      "label": "AdPilot",
      "service": "adpilot",
      "route": "/adpilot",
      "page": "northstar-os-ui/src/pages/internal/AdPilot.jsx",
      "page_title": "AdPilot",
      "page_anchor": "[data-testid=\"ap-bulk-action\"]",
      "scene": {
        "id": "adpilot",
        "label": "Meteor Rain",
        "variant": "meteor-rain"
      },
      "views": {
        "param": "view",
        "default": "campaigns",
        "tabs_rendered_by": "page",
        "tabs": [
          {
            "id": "campaigns",
            "label": "Campaigns"
          },
          {
            "id": "detail",
            "label": "Campaign Detail"
          },
          {
            "id": "terms",
            "label": "Search Terms"
          },
          {
            "id": "harvest",
            "label": "Harvest"
          },
          {
            "id": "planner",
            "label": "Planner"
          },
          {
            "id": "creatives",
            "label": "Creatives"
          },
          {
            "id": "placements",
            "label": "Placements"
          },
          {
            "id": "rules",
            "label": "Rules"
          }
        ]
      },
      "bojo_tool": {
        "id": "plan_campaign",
        "status": "wired",
        "owner": "adpilot",
        "source": "ty/bojo_tool_list.json",
        "note": "chat_tools.TOOLS['plan_campaign'] proposes a campaign from supplied facts; it never pushes to an ad platform."
      },
      "gate": {
        "entitlement_key": "studio.adpilot",
        "decided_by": "northstar-os-ui/src/lib/serviceGate.js::canUseService",
        "dev": "dev_open",
        "denied": "no studio credit"
      },
      "why": "PPC work is a loop - read the campaigns, open one, mine the search terms, harvest the winners, then plan the next pass - so the tabs are that loop in order, with detail as a tab rather than a modal."
    },
    {
      "id": "golden-goose",
      "click_path_view": "review",
      "core_role": "golden-goose",
      "label": "Golden Goose",
      "service": "golden-goose",
      "route": "/golden-goose",
      "page": "northstar-os-ui/src/pages/internal/GoldenGoose.jsx",
      "page_title": "Golden Goose Finder",
      "page_anchor": "nav[aria-label=\"Service navigation\"]",
      "scene": {
        "id": "golden-goose",
        "label": "Pulsar Heart",
        "variant": "crab-pulsar"
      },
      "views": {
        "param": "view",
        "default": "queue",
        "tabs_rendered_by": "page",
        "tabs": [
          {
            "id": "queue",
            "label": "Queue"
          },
          {
            "id": "review",
            "label": "Review"
          },
          {
            "id": "decisions",
            "label": "Decisions"
          },
          {
            "id": "history",
            "label": "History"
          }
        ]
      },
      "bojo_tool": {
        "id": "golden_goose_scan",
        "status": "wired",
        "owner": "goldengoose",
        "source": "ty/bojo_tool_list.json",
        "note": "chat_tools.TOOLS['golden_goose_scan'] scores candidates and returns the arithmetic; the tool's also_used_by names golden-goose."
      },
      "gate": {
        "entitlement_key": "studio.golden-goose",
        "decided_by": "northstar-os-ui/src/lib/serviceGate.js::canUseService",
        "dev": "dev_open",
        "denied": "no studio credit"
      },
      "why": "A sourcing queue only earns a screen if review, decision and history sit beside it - the queue is worthless without the trail of what was decided and why."
    },
    {
      "id": "product-finder",
      "click_path_view": "set",
      "core_role": "research",
      "label": "SourceScout",
      "service": "product-finder",
      "route": "/product-finder",
      "page": "northstar-os-ui/src/pages/internal/ProductFinder.jsx",
      "page_title": "SourceScout",
      "page_anchor": "[data-testid=\"pf-asin-input\"]",
      "scene": {
        "id": "product-finder",
        "label": "Orion Cradle",
        "variant": "orion-nursery"
      },
      "views": {
        "param": "view",
        "default": "lookup",
        "tabs_rendered_by": "page",
        "tabs": [
          {
            "id": "lookup",
            "label": "Lookup"
          },
          {
            "id": "set",
            "label": "Product Set"
          },
          {
            "id": "saved",
            "label": "Saved Sets"
          },
          {
            "id": "coverage",
            "label": "Coverage"
          }
        ]
      },
      "bojo_tool": {
        "id": "scan_products",
        "status": "wired",
        "owner": "product-finder",
        "source": "ty/bojo_tool_list.json",
        "note": "chat_tools.TOOLS['scan_products'] runs the local scanner; every row it returns carries its own source badge."
      },
      "gate": {
        "entitlement_key": "studio.product-finder",
        "decided_by": "northstar-os-ui/src/lib/serviceGate.js::canUseService",
        "dev": "dev_open",
        "denied": "no studio credit"
      },
      "why": "Product research moves one product at a time from a lookup, into a set, into a saved set with a coverage statement, so the four tabs are the four states a candidate can be in."
    },
    {
      "id": "product-pictures",
      "click_path_view": "workspace",
      "core_role": "product-pictures",
      "label": "Product Pictures",
      "service": "product-pictures",
      "route": "/product-pictures",
      "page": "northstar-os-ui/src/pages/internal/ProductPictures.jsx",
      "page_title": "Product Pictures",
      "page_anchor": "[data-testid=\"listing-images-workspace\"]",
      "scene": {
        "id": "product-pictures",
        "label": "Carina Ridge",
        "variant": "carina-cliffs"
      },
      "views": {
        "param": "",
        "default": "workspace",
        "tabs_rendered_by": "page",
        "tabs": [
          {
            "id": "workspace",
            "label": "Picture workspace"
          }
        ]
      },
      "bojo_tool": {
        "id": "generate_image",
        "status": "wired",
        "owner": "design-studio",
        "source": "ty/bojo_tool_list.json",
        "note": "No product_picture tool is wired in chat_tools yet, so this surface opens the shared generate_image lane rather than claiming a tool it does not have."
      },
      "gate": {
        "entitlement_key": "studio.product-pictures",
        "decided_by": "northstar-os-ui/src/lib/serviceGate.js::canUseService",
        "dev": "dev_open",
        "denied": "no studio credit"
      },
      "why": "One job - the main image and its secondary modules for a single listing - so it gets one view and no tab strip: the format, slot and compliance rails already live inside the surface."
    }
  ]
}

export default WORKSPACE_SPECS
