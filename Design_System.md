# Design System Document: The Kinetic Editorial

## 1. Overview & Creative North Star
**Creative North Star: "The Digital Atelier"**
This design system moves away from the rigid, boxed-in nature of traditional e-commerce. It treats the interface as a high-end fashion editorial—dynamic, spacious, and authoritative. We lean into **Organic Minimalism**, where the product photography acts as the primary architectural element, and the UI serves as a sophisticated, quiet frame.

By utilizing intentional asymmetry, overlapping typography, and a "layering" approach to surfaces, we break the "template" look. We are not just building a store; we are creating a curated gallery experience that builds trust through precision and restraint.

---

## 2. Colors & Surface Philosophy
Our palette is rooted in the high-contrast tension between `primary` (Black) and `surface` (Crisp White/Off-White), punctuated by a high-energy `on_primary_container` (Vibrant Orange) to drive conversion.

### The "No-Line" Rule
**Strict Mandate:** Traditional 1px solid borders are prohibited for sectioning or containment. 
Structure is defined through:
*   **Background Shifts:** Distinguish the "New Arrivals" section from the "Hero" by transitioning from `surface` to `surface_container_low`.
*   **Negative Space:** Use generous margins to create "invisible" gutters that guide the eye.

### Surface Hierarchy & Nesting
Treat the UI as physical layers of fine paper. 
*   **Level 0 (Base):** `surface` (#fcf9f8) - The foundational canvas.
*   **Level 1 (Sections):** `surface_container_low` (#f6f3f2) - Subtle differentiation for secondary content blocks.
*   **Level 2 (Interaction):** `surface_container_highest` (#e5e2e1) - Active areas or hover states.
*   **Level 3 (Floating):** `surface_container_lowest` (#ffffff) - Reserved for product cards to make them "pop" against a tinted background.

### The "Glass & Gradient" Rule
To elevate the "Modern" brand pillar, use Glassmorphism for floating navigation bars or quick-buy overlays. Apply `surface` at 70% opacity with a `24px` backdrop-blur. 
*   **Signature Polish:** For primary CTAs, use a subtle linear gradient from `primary` (#000000) to `primary_container` (#3a0b00) at a 145-degree angle to give buttons a "milled" metallic depth.

---

## 3. Typography
We utilize a dual-typeface system to balance high-fashion editorial impact with utilitarian clarity.

*   **The Display Voice (Manrope):** Our "Heading" font. It is geometric and modern. Use `display-lg` for hero statements with tight letter-spacing (-0.02em) to create an authoritative, premium feel.
*   **The Utility Voice (Inter):** Our "Body" font. Highly legible and neutral. Use `body-md` for all product descriptions and `label-md` for technical specifications.

**Editorial Hierarchy:**
*   **Headlines:** Always use `on_surface` (#1c1b1b). Use `headline-lg` for category titles.
*   **Captions:** Use `on_surface_variant` (#4c4546) for secondary details to reduce visual noise.

---

## 4. Elevation & Depth
We eschew the "standard drop shadow" in favor of **Tonal Layering**.

### The Layering Principle
Depth is achieved by stacking. A `surface_container_lowest` card sitting on a `surface_container` background creates a natural, soft lift. This mimics how a physical shoe box sits on a gallery floor.

### Ambient Shadows
If a floating element (like a Cart Drawer) requires a shadow, it must be an **Ambient Shadow**:
*   **Y-Offset:** 12px | **Blur:** 40px | **Spread:** -4px.
*   **Color:** `on_surface` at 6% opacity. This creates a soft glow rather than a harsh edge.

### The "Ghost Border" Fallback
If an edge is required for accessibility (e.g., in high-contrast modes), use a **Ghost Border**: `outline_variant` at 15% opacity. Never use 100% opaque lines.

---

## 5. Components

### Buttons
*   **Primary (Action):** Background `on_primary_container` (Vibrant Orange), Text `on_primary`. Roundedness: `md` (0.75rem). No shadow.
*   **Secondary (Editorial):** Background `primary` (Black), Text `on_primary`.
*   **Tertiary (Ghost):** No background. Text `primary`. Use a subtle underline (1px) that expands on hover.

### Product Cards
*   **Styling:** Forbid dividers. Use `surface_container_lowest` for the card body against a `surface_container_low` page background.
*   **Corners:** `md` (0.75rem / 12px) for the main container.
*   **Photography:** Images should be full-bleed with a subtle `2px` inset of whitespace to create a "framed" look.

### Input Fields
*   **Visual State:** Instead of a full box, use a `surface_container` background with a `sm` (0.25rem) corner radius.
*   **Active State:** The background remains static, but the `primary` color appears as a 2px bottom-indicator line.

### Interactive Micro-Chips
*   **Purpose:** Size selection and color filtering.
*   **Style:** `outline_variant` "Ghost Borders." When selected, the chip fills with `primary` and text flips to `on_primary`.

---

## 6. Do's and Don'ts

### Do
*   **DO** use "Aggressive Whitespace." If you think there is enough space between sections, double it.
*   **DO** use `display-lg` typography that occasionally overlaps product imagery for a custom editorial feel.
*   **DO** prioritize high-quality, desaturated product photography to maintain the "Luxury" vibe.

### Don't
*   **DON'T** use 1px solid black borders. It cheapens the "High-End" brand.
*   **DON'T** use standard "Blue" for links. Use `primary` (Black) with an underline or the `on_primary_container` (Orange) for critical actions.
*   **DON'T** use heavy drop shadows on cards. Let the background color shifts do the heavy lifting for hierarchy.
