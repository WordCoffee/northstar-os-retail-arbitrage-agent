// PRODUCT PICTURES — the picture half of the studio, on its own route.
//
// The surface is not a copy: it is the Design Studio's Listing Images section
// (`design-studio/ListingImages.jsx`), which already carries the spec registry,
// the safe-zone canvas, the slot rail and the compliance pre-flight. What this
// page adds is the thing that section never had on its own — a route, a scene,
// a tab and a workspace spec of its own (`ty/northstar_workspaces.json`), so an
// operator whose job is "the pictures for this listing" is not asked to find a
// section picker inside a twelve-section studio first.
//
// Honest limit, stated where it is rendered: no product_picture tool is wired
// in chat_tools yet, so the workspace opens the shared generate_image lane.

import { PageLayout } from '../../components/Shared.jsx'
import ListingImages from './design-studio/ListingImages.jsx'

export default function ProductPictures() {
  return (
    <PageLayout
      title="Product Pictures"
      subtitle="The main image and its secondary modules for one listing — the studio's Listing Images surface, on its own route."
    >
      <div data-testid="product-pictures">
        <ListingImages />
      </div>
    </PageLayout>
  )
}
