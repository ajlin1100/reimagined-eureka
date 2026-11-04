# Smith IT Page-Type Style Guide

## Purpose

This guide translates the Smith Style Guide into page patterns for the Smith IT rebuild. It captures the visual language already established in the revised pages while giving informational, directional, and illustrative pages distinct treatments.

The Smith Style Guide remains authoritative for brand use. This document is a page-design supplement, not a replacement.

## Page Classification

| Page | Primary type | Why |
|---|---|---|
| [Acceptable Use Guidelines](../pages/about_smith_it%20ribbon/2_acceptable_use_guidelines/content.html) | Informational / policy | Readers need to understand and reference policy sections, requirements, and addenda. |
| [Operating Hours and Who to Call](../pages/about_smith_it%20ribbon/1_about_smith_it/content.html) | Directional / service routing | The page helps visitors choose the right service desk, contact, location, or request path. It is information-dense, but its primary job is to direct action. |
| [New Faculty IT Guide](../pages/getting_started%20ribbon/1_new_faculty/content.html) | Directional / onboarding | The page organizes a sequence of setup tasks and gives each task an action or contact path. |
| [The Office of Smith IT](../pages/about_smith_it%20ribbon/3_about_us/content.html) | Illustrative / people directory | The page introduces staff and teams through portraits, roles, contact details, and biographies. |

A page can contain supporting content from another type. Classify it by its primary user task, then use secondary patterns sparingly. For example, Operating Hours includes reference tables, but its main purpose is still service routing.

## Shared Smith Foundation

Use these foundations across all three page types. Each page type may change density, layout, and component treatment, but not the Smith brand identity.

### Color

Use the official guide tokens and assign them consistent roles:

| Token | Value | Role |
|---|---|---|
| Smith red | `#ba182e` | Primary accent, links, section rules, and primary actions |
| Dark Smith red | `#8d1324` | Hover and pressed states; a restrained darker red for emphasis |
| Smith yellow | `#ffc845` | Secondary accent, small highlights, and paired rules or borders |
| Black | `#000000` | Headings and high-emphasis text |
| Dark gray | `#454545` | Body copy |
| Medium gray | `#7f7f7f` | Supporting labels and secondary metadata |
| Light gray | `#e6e6e6` | Borders and dividers |
| Lighter gray | `#f7f7f7` | Quiet panel and page surfaces |
| White | `#ffffff` | Content surfaces and reversed text |

For this rebuild, replace legacy blue UI accents with Maryland red and its darker tint. Use yellow as a supporting accent rather than a second dominant color. Keep most page area white or neutral gray. Do not introduce unrelated accent hues for decoration.

### Typography and Shape

- Use Source Sans 3, with a sans-serif fallback.
- Keep body text at least `12pt`, with a line height around `1.6`; use weight and spacing to create hierarchy.
- Use black for headings and dark gray for paragraph text. Red is for emphasis, links, and actions, not long passages.
- Use the guide's `10px` radius as the maximum standard corner radius. Page-type guidance below may use square corners for formal panels.
- Keep borders and shadows restrained. Use borders, rules, spacing, and surface contrast to distinguish adjacent content.
- When retaining emoji from source content, use the Unicode text-presentation selector (`U+FE0E`) so glyphs render monochromatically rather than as full-color emoji.

### Interaction and Accessibility

- Links must remain visibly distinct from body text, typically red, bold, and underlined. Buttons are filled red for primary actions; do not style ordinary inline links as buttons.
- Provide clear hover and keyboard-focus states. Never make color the only way to communicate status or meaning.
- Preserve semantic headings, meaningful link text, table headers, and descriptive alt text for staff portraits.
- Keep grids responsive. On narrow screens, stack columns; make wide tables horizontally scrollable; move sticky navigation into normal document flow.
- Maintain readable contrast for all text, labels, and controls.

## Style Guide 1: Informational and Policy Pages

**Primary example:** Acceptable Use Guidelines.

**Use when:** The visitor needs to read, understand, or return to authoritative material. The content is long-form, structured, or policy-oriented rather than a sequence of actions.

### Composition

- Use the shared white header: short red rule, red uppercase eyebrow, black title, dark-gray summary, and yellow bottom rule.
- Put long-form content on white, with a thin light-gray border and clear section spacing. Prefer square corners and no shadow for formal policy sections.
- Use a restrained light-gray page surface around the content where it improves separation.
- For lengthy documents, provide a table of contents or side navigation. Sticky navigation is suitable on desktop; stack it above the content on mobile.
- Keep policy metadata in a compact banner with a red leading border and a subtle red/yellow tint.

### Hierarchy and Callouts

- Give section headings a neutral divider and a short red underline.
- Reserve pale red callouts with a red border for prohibited conduct, risk, or other critical policy content. Keep the callout's heading and text explicit; color alone is not the signal.
- Separate school-specific addenda from institutional policy with a red top rule. A short yellow accent can distinguish a secondary heading within the addendum.
- Keep inline links red, bold, and underlined. Avoid decorative cards around ordinary paragraphs.

### Example Components

`policy-page-container`, `meta-banner`, `policy-grid`, `sticky-nav`, `policy-section`, `prohibited-box`, and `addendum-card`.

## Style Guide 2: Directional and Task-Oriented Pages

**Primary examples:** Operating Hours and Who to Call; New Faculty IT Guide.

**Use when:** The visitor needs to decide where to go, whom to contact, or what to do next. This category includes both service-routing pages and step-by-step onboarding pages.

### Composition

- Use the shared white header and red/yellow rules for standard directional pages. Give the title and summary enough room to orient the visitor before presenting options.
- Arrange comparable choices in responsive grids. Use headings, labels, and consistent spacing so locations, services, or steps can be scanned quickly.
- Keep each info box, checklist item, and section visibly enclosed using a neutral surface, thin gray outline, and a brand-colored edge or rule.
- Use numbered circular badges for ordered sections or steps when sequence matters. Red fill with a yellow outline keeps the number prominent.
- Prefer tables for schedules and similarly structured facts. Preserve clear headers and alignment; do not turn dense data into prose cards unnecessarily.

### Routing and Actions

- Make the recommended route or important instruction easy to find with a compact red-edged banner.
- Use filled red buttons for primary actions and white/red outlined buttons for secondary actions. Keep inline links underlined and visually separate from buttons.
- Use a pale yellow or neutral surface with a red edge for general notices. Reserve stronger pale-red treatment for critical or urgent information.
- For support contacts, group channels together and keep the email address or phone number easy to scan.

### Variants

**Service routing (Operating Hours):** Use compact hours cards, location labels, aligned schedule tables, an emergency-support callout, and a clear primary Service Desk recommendation. Use two- or three-column grids only while the content remains readable.

**Onboarding (New Faculty):** Use numbered sections, neutral-tinted info boxes, ordered checklist panels, and a clear action button within each task when one exists. Use a distinct contact banner for immediate support. Keep each task's title, explanation, and action together.

### Example Components

Operating Hours: `notice-banner`, `hours-card`, `hours-table`, `location-badge`, `btn-action`, `emergency-card`, and `styled-table`.

New Faculty: `section-card`, `badge`, `info-box`, `checklist-item`, `notice-box`, `notice-box-danger`, and `btn-link`.

## Style Guide 3: Illustrative and People Pages

**Primary example:** The Office of Smith IT / staff roster.

**Use when:** The page's main purpose is to introduce people, teams, places, or institutional identity. Images and short descriptions carry meaningful information, rather than merely decorating the page.

### Composition

- A solid or red-to-dark-red header with a yellow left edge is an approved page-type variation for a people directory. Use it selectively; informational and directional pages use the white editorial header by default.
- Group people by team or function using clear section headings and a short red rule.
- Use a responsive roster grid with consistent card widths and portrait dimensions. Keep the card white with a thin gray border and a red top rule; avoid heavy shadows.
- Use real, relevant portraits with descriptive alt text. Keep image crops and dimensions consistent so the grid feels orderly.
- Make names and roles the primary text hierarchy. Keep biographies concise and secondary.

### Contact Details

- Group email and phone information in a compact, light-gray contact panel. A yellow edge may mark this supporting contact area.
- Style email links in red with a clear hover or focus state. Do not let contact details compete with the person's name and role.
- Use consistent labels and formatting across all roster entries, including vacant positions.

### Example Components

`roster-section-title`, `section-lead`, `staff-grid`, `staff-card`, `avatar-container`, `staff-title`, `contact-box`, and `bio-text`.

## Choosing a Page Type

Ask what the visitor primarily came to do:

1. **Understand or reference information:** use the informational/policy guide.
2. **Find a service, contact, location, or next step:** use the directional guide.
3. **Recognize people, teams, or institutional identity:** use the illustrative guide.

If the page has more than one job, choose one primary type for its header and overall composition. Borrow only the components needed from a secondary type; keep its visual accents subordinate so the page remains coherent.

## Source Pages

- [Smith Style Guide](smith_style_guide.html)
- [Operating Hours and Who to Call](../pages/about_smith_it%20ribbon/1_about_smith_it/content.html)
- [Acceptable Use Guidelines](../pages/about_smith_it%20ribbon/2_acceptable_use_guidelines/content.html)
- [The Office of Smith IT](../pages/about_smith_it%20ribbon/3_about_us/content.html)
- [New Faculty IT Guide](../pages/getting_started%20ribbon/1_new_faculty/content.html)
