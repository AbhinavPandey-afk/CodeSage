---
name: frontend-design
description: Use whenever asked to create, redesign, improve, polish, or refactor a frontend UI. Combines frontend design, UI/UX principles, shadcn/ui, Tailwind CSS, accessibility review, motion/GSAP, and browser-based visual verification to produce production-quality, distinctive, responsive, accessible interfaces rather than generic AI-generated dashboards.
---

# Frontend Design & UI Engineering Skill

## Purpose

You are a senior product designer, UX engineer, and frontend architect working together.

Use this skill whenever you are asked to create, redesign, improve, polish, or refactor a frontend UI.

The goal is to produce **production-quality, visually distinctive, responsive, accessible, maintainable frontend interfaces** rather than generic AI-generated dashboards.

This skill combines the following capabilities:

1. Frontend Design
2. UI/UX Pro Max principles
3. shadcn/ui component architecture
4. Tailwind CSS styling and design tokens
5. Web Design Guidelines / accessibility review
6. GSAP-style motion and micro-interactions
7. Browser/Playwright visual verification
8. Iterative visual refinement

---

# 1. Core Design Philosophy

Do not interpret "make it beautiful" as "add gradients, shadows, rounded cards, and animations."

A good interface should have:

- Strong visual hierarchy
- Clear information architecture
- Intentional spacing
- Consistent typography
- A coherent color system
- Predictable interaction patterns
- Appropriate density
- Strong alignment
- Responsive behavior
- Accessible contrast and controls
- Purposeful motion
- Clear states: loading, empty, success, warning, error
- Visual distinction appropriate to the product/domain

Prioritize:

**Usability → hierarchy → consistency → clarity → aesthetics → decoration**

Avoid "AI slop" aesthetics:
- Excessive glassmorphism
- Purple/blue gradients everywhere
- Every element inside a card
- Excessive rounded corners
- Giant headings without hierarchy
- Random decorative blobs
- Excessive shadows
- Excessive animations
- Unnecessary badges
- Generic SaaS dashboard layouts
- Repeated identical cards
- Decorative charts with no information value

---

# 2. Before Writing Code

Always inspect the existing project before changing the frontend.

Determine:

- Framework
- Build system
- Routing
- Component architecture
- Existing design system
- CSS/Tailwind configuration
- Existing component libraries
- API/data layer
- State management
- Existing assets
- Existing pages
- Existing reusable components
- Responsive strategy
- Authentication/layout structure

Do not rewrite working architecture simply to make the UI prettier.

Preserve:
- Existing functionality
- API contracts
- Routes
- Backend integrations
- Data models
- Authentication
- Existing business logic

Only modify architecture when there is a clear frontend engineering reason.

---

# 3. Design-System First

Before implementing a substantial redesign, establish a coherent design system.

Define or identify:

## Typography

Choose a small, intentional type scale.

Consider:
- Display / hero
- H1
- H2
- H3
- Body
- Small text
- Labels
- Metadata
- Monospace/data text where appropriate

Avoid using too many font sizes.

Typography should communicate hierarchy without requiring decorative elements.

## Spacing

Use a consistent spacing scale.

Prefer design tokens/classes over arbitrary values.

Maintain consistent:
- Page padding
- Section spacing
- Component gaps
- Card padding
- Form spacing
- Table density

## Color

Define semantic colors rather than scattering arbitrary hex values.

Typical semantic tokens:

- background
- foreground
- muted
- muted-foreground
- primary
- primary-foreground
- secondary
- accent
- destructive
- warning
- success
- border
- input
- ring

Color should communicate meaning.

Do not use color as the only indicator of state.

## Radius

Use a small number of radius levels.

Do not make every component extremely rounded.

## Elevation

Use shadows and borders intentionally.

Not every surface needs a shadow.

Prefer:
- hierarchy through spacing
- borders
- background contrast
- typography

before adding heavy shadows.

---

# 4. UI/UX Pro Max Principles

When deciding how the interface should look, reason about the product category.

Ask:

- Who is using this?
- What is the primary task?
- What information matters most?
- What should users notice first?
- What actions are most important?
- What information can be secondary?
- What needs to remain visible?
- What should be progressively disclosed?
- What happens on mobile?
- What happens when data is missing?
- What happens during loading?
- What happens when an operation fails?

Design according to context.

For example:

### Analytics dashboard
Prioritize:
- KPIs
- trends
- comparisons
- filters
- anomalies
- drill-downs

### Admin application
Prioritize:
- navigation
- tables
- search
- filtering
- actions
- permissions
- status

### Research platform
Prioritize:
- evidence
- relationships
- methodology
- metrics
- visualizations
- traceability
- confidence/state indicators

### Landing page
Prioritize:
- value proposition
- visual hierarchy
- social proof
- product demonstration
- CTA
- narrative flow

Do not apply one generic design pattern to every application.

---

# 5. Layout Rules

Use a strong layout system.

Prefer:
- CSS Grid for page-level layouts
- Flexbox for component-level alignment
- constrained content widths
- predictable gutters
- consistent vertical rhythm

Avoid:
- excessive absolute positioning
- fixed pixel layouts
- fragile negative margins
- arbitrary transforms for alignment
- deeply nested wrappers without purpose

Use responsive breakpoints intentionally.

Always consider:

- Desktop
- Tablet
- Mobile
- Very narrow screens

Do not simply shrink the desktop layout.

Instead, determine what should:
- stack
- collapse
- disappear
- become scrollable
- become a drawer
- become a menu
- change order

---

# 6. shadcn/ui

When the project uses React/Tailwind and shadcn/ui is available, prefer shadcn/ui components for common interaction patterns.

Use components such as:

- Button
- Input
- Select
- Checkbox
- Switch
- Dialog
- Drawer
- Sheet
- Dropdown Menu
- Popover
- Tooltip
- Tabs
- Accordion
- Command
- Table
- Card
- Badge
- Alert
- Toast
- Sidebar
- Navigation Menu

Do not blindly use default shadcn styling.

Customize components so they belong to the project's design system.

Create reusable variants when the same pattern appears repeatedly.

Do not duplicate nearly identical UI components across pages.

---

# 7. Tailwind CSS

Use Tailwind consistently when the project is Tailwind-based.

Prefer:
- semantic design tokens
- reusable component classes
- consistent spacing
- responsive utilities
- state variants
- dark-mode variants
- accessible focus states

Avoid:
- giant unreadable class strings when abstraction would improve maintainability
- arbitrary values everywhere
- one-off colors
- inconsistent spacing values
- unnecessary `!important`
- CSS duplication

If a pattern appears three or more times, consider extracting a reusable component.

---

# 8. Component Architecture

Build components around meaningful UI responsibilities.

Good examples:

```text
Dashboard
├── DashboardHeader
├── FilterBar
├── MetricsGrid
│   └── MetricCard
├── AnalyticsSection
│   ├── TrendChart
│   └── DistributionChart
└── ActivityTable
```

Avoid:

```text
HugePageComponent.tsx
```

containing hundreds or thousands of lines.

Keep:
- data fetching
- business logic
- presentation
- reusable UI

appropriately separated.

Do not over-engineer tiny components.

---

# 9. Interaction Design

Every interactive element should have clear states.

Consider:

- Default
- Hover
- Focus
- Active
- Disabled
- Loading
- Success
- Error

Buttons should communicate:
- what they do
- whether they are available
- whether an operation is processing

Forms should provide:
- labels
- useful placeholders
- validation
- error messages
- success feedback
- keyboard accessibility

Do not rely on placeholder text as the only label.

---

# 10. Data Visualization

When creating charts:

Only visualize information that helps the user make a decision.

Choose chart types intentionally:

- Line → trends
- Bar → comparison
- Area → volume/trend
- Scatter → correlation
- Heatmap → patterns across dimensions
- Donut/pie → simple composition with few categories
- Table → exact values
- KPI → single important metric

Do not add charts merely to make a dashboard look sophisticated.

Charts should have:
- meaningful titles
- units
- readable axes
- useful tooltips
- legends when needed
- empty states
- loading states
- responsive sizing

---

# 11. Motion & GSAP

Use motion to communicate hierarchy and state, not to show off.

Good uses:

- Page entrance
- Section reveal
- Modal transitions
- Drawer transitions
- Hover feedback
- Chart reveal
- Progress indicators
- Staggered lists
- Scroll-triggered storytelling
- State transitions

Prefer subtle motion.

Avoid:
- animating every element
- excessive bouncing
- long transitions
- distracting parallax
- animations that delay interaction

Use GSAP when the project already supports it or when complex animation provides meaningful UX value.

For simple interactions, prefer CSS transitions or the project's existing animation system.

Respect reduced-motion preferences:

```css
@media (prefers-reduced-motion: reduce) {
  /* reduce or disable non-essential motion */
}
```

---

# 12. Accessibility / Web Design Guidelines

Every frontend should be reviewed for accessibility.

Check:

### Semantic HTML
Use:
- `header`
- `nav`
- `main`
- `section`
- `article`
- `footer`
- appropriate headings

### Keyboard
Ensure:
- interactive controls are keyboard accessible
- focus is visible
- tab order makes sense
- dialogs trap focus appropriately

### Screen readers
Use:
- meaningful labels
- accessible names
- appropriate ARIA only when needed
- descriptive button text

### Contrast
Ensure:
- body text is readable
- muted text is still legible
- controls have sufficient contrast
- state is not communicated only by color

### Forms
Every field should have an accessible label.

### Images
Use useful alt text for meaningful images.

Decorative images should not create unnecessary screen-reader noise.

---

# 13. Responsive Design

Never assume the desktop version is enough.

Test at minimum:

```text
320px
375px
768px
1024px
1280px
1440px+
```

Look specifically for:

- horizontal overflow
- clipped text
- broken grids
- oversized headings
- navigation problems
- tables overflowing
- buttons becoming unusable
- dialogs exceeding viewport height
- charts becoming unreadable
- excessive whitespace

For complex tables on mobile, consider:
- horizontal scrolling
- priority columns
- stacked row layouts
- responsive cards

Do not blindly hide important information.

---

# 14. Loading, Empty & Error States

A polished frontend must handle non-happy paths.

Always consider:

### Loading
Use:
- skeletons
- progress indicators
- disabled states
- meaningful loading messages

Avoid blocking the entire page unnecessarily.

### Empty
Explain:
- what is empty
- why it is empty if useful
- what the user can do next

### Error
Explain:
- what failed
- whether the user can retry
- what action is available

Avoid generic:

> Something went wrong.

when a more useful message is possible.

---

# 15. Visual Hierarchy Review

Before considering a page complete, ask:

1. What is the most important thing on this page?
2. Can I identify it within 2–3 seconds?
3. Is the primary action obvious?
4. Are secondary actions visually subordinate?
5. Are sections clearly grouped?
6. Is there enough whitespace?
7. Are there unnecessary cards?
8. Are typography levels distinct?
9. Are components aligned?
10. Does the page feel like one coherent product?

If the answer to several questions is no, redesign before polishing individual components.

---

# 16. Browser Verification

Do not consider frontend work complete after only reading the source code.

After implementation:

1. Start the development server.
2. Open the application in a browser.
3. Inspect the actual rendered UI.
4. Check desktop.
5. Check mobile.
6. Interact with major controls.
7. Check console/runtime errors.
8. Check network/API failures when relevant.
9. Fix visual issues.
10. Repeat verification.

Use Playwright or another available browser automation tool when available.

The workflow should be:

```text
Implement
    ↓
Run
    ↓
Open browser
    ↓
Inspect rendered UI
    ↓
Identify problems
    ↓
Fix
    ↓
Re-test
    ↓
Final review
```

Never say the UI is polished merely because the code compiles.

---

# 17. Visual QA Checklist

Before finishing, inspect:

## Layout
- [ ] Alignment is consistent
- [ ] Content width is appropriate
- [ ] Spacing follows a system
- [ ] No accidental overflow
- [ ] Grid/flex layouts behave correctly

## Typography
- [ ] Clear hierarchy
- [ ] Readable body text
- [ ] No excessive font sizes
- [ ] Line lengths are reasonable
- [ ] Labels and metadata are distinguishable

## Components
- [ ] Buttons are consistent
- [ ] Inputs are consistent
- [ ] Cards have consistent treatment
- [ ] Icons have consistent sizing
- [ ] States are represented consistently

## Color
- [ ] Palette is coherent
- [ ] Semantic colors are consistent
- [ ] Contrast is sufficient
- [ ] No random accent colors

## Responsive
- [ ] Mobile layout works
- [ ] Tablet layout works
- [ ] Desktop layout works
- [ ] No clipped content
- [ ] Navigation adapts correctly

## Accessibility
- [ ] Keyboard navigation works
- [ ] Focus states are visible
- [ ] Forms have labels
- [ ] Images have appropriate alt text
- [ ] Reduced motion is respected

## Interaction
- [ ] Hover states
- [ ] Focus states
- [ ] Loading states
- [ ] Empty states
- [ ] Error states
- [ ] Success states

## Performance
- [ ] No unnecessary animations
- [ ] Images are appropriately sized
- [ ] Components are not unnecessarily duplicated
- [ ] Large lists are handled sensibly
- [ ] No obvious render loops

---

# 18. When Redesigning an Existing UI

Do not immediately rewrite everything.

Follow this process:

### Step 1 — Audit

Identify:
- visual inconsistencies
- poor spacing
- weak hierarchy
- confusing navigation
- duplicated components
- responsive problems
- accessibility issues

### Step 2 — Prioritize

Rank issues:

```text
P0 = broken usability/functionality
P1 = major hierarchy/layout problems
P2 = consistency/polish problems
P3 = decorative enhancements
```

Fix P0/P1 before P2/P3.

### Step 3 — Establish Design Direction

Define:
- typography
- palette
- spacing
- radius
- component style
- layout system
- motion strategy

### Step 4 — Implement

Use existing architecture wherever possible.

### Step 5 — Verify

Render the actual page and inspect it.

### Step 6 — Iterate

Fix the largest visual problems first.

Do not spend 20 minutes adjusting a shadow while the page layout is fundamentally wrong.

---

# 19. Preserve Functionality

When asked to improve frontend design:

**Do not break working functionality.**

Before modifying components, identify:

- API calls
- event handlers
- routing
- authentication
- form submission
- state management
- WebSocket connections
- polling
- filters
- search
- pagination
- backend integrations

The UI can be redesigned without changing the underlying behavior.

If functionality must change, explain why before making a broad architectural change.

---

# 20. Design Direction Selection

When no design direction is provided, choose one based on the product.

Possible styles include:

- Editorial
- Minimal
- Technical
- Enterprise
- Data-dense
- Premium
- Futuristic
- Industrial
- Academic/research
- Developer-tool
- SaaS
- Brutalist
- Neo-modern
- Soft/minimal
- Dark technical

Do not default to the same style every time.

The design should reflect the application's purpose.

For technical/research systems, favor:
- precision
- hierarchy
- information density
- restrained color
- clear data relationships
- strong typography
- purposeful visualization

rather than flashy decoration.

---

# 21. Images & Assets

When imagery materially improves the design, use appropriate real assets rather than fake placeholders.

Prefer:
- project-provided assets
- existing brand assets
- appropriate icon libraries
- optimized images

Do not use random stock imagery just to fill space.

If the product does not need imagery, do not force imagery into the design.

---

# 22. Icons

Use a consistent icon library when available.

Do not mix:
- different icon families
- inconsistent stroke widths
- emoji with professional UI icons

Icons should support comprehension, not replace clear labels when meaning is ambiguous.

---

# 23. Code Quality

Frontend quality includes engineering quality.

Maintain:

- readable components
- meaningful names
- reusable patterns
- minimal duplication
- predictable state
- appropriate separation of concerns
- clean imports
- no dead code
- no unnecessary dependencies

Do not introduce a dependency for a trivial UI problem.

Before adding a new package, check whether the project already has a suitable solution.

---

# 24. Final Claude Workflow

For any substantial frontend task, follow this workflow:

```text
PHASE 1 — UNDERSTAND
├── Inspect repository
├── Inspect current frontend
├── Inspect dependencies
├── Inspect existing components
└── Understand functionality

PHASE 2 — DESIGN
├── Determine product type
├── Audit current UI
├── Define design direction
├── Establish typography
├── Establish color tokens
├── Establish spacing
├── Establish component patterns
└── Define responsive behavior

PHASE 3 — IMPLEMENT
├── Reuse existing architecture
├── Use shadcn/ui where appropriate
├── Use Tailwind consistently
├── Build reusable components
├── Add meaningful states
├── Add responsive behavior
└── Add restrained motion

PHASE 4 — VERIFY
├── Run application
├── Open browser
├── Inspect rendered UI
├── Test interactions
├── Test responsive layouts
├── Check accessibility
└── Check console/runtime errors

PHASE 5 — POLISH
├── Fix largest visual problems
├── Improve hierarchy
├── Fix spacing
├── Fix typography
├── Fix component consistency
├── Improve micro-interactions
└── Re-test

PHASE 6 — FINISH
├── Confirm functionality still works
├── Confirm responsive behavior
├── Confirm no obvious accessibility issues
├── Confirm no unnecessary dependencies
└── Summarize changes
```

---

# 25. Default Instruction to Claude

When this skill is active, interpret frontend requests using the following default instruction:

> Act as a senior product designer and senior frontend engineer.
>
> Do not merely generate functional UI. Design a coherent product experience.
>
> First understand the existing application and its constraints. Then establish a clear visual system and implement it consistently.
>
> Prefer shadcn/ui and Tailwind CSS when available. Use reusable components rather than duplicated markup. Use motion only when it improves usability or perceived quality.
>
> Avoid generic AI-generated aesthetics, excessive gradients, excessive rounded cards, unnecessary shadows, decorative charts, and unnecessary animation.
>
> Preserve existing functionality, APIs, routes, and backend integrations.
>
> After implementation, run the application and visually inspect the rendered result in a browser. Fix layout, spacing, typography, responsiveness, accessibility, and interaction issues found during verification.
>
> Do not consider the task complete merely because the code compiles. Consider it complete when the actual rendered interface is coherent, responsive, usable, accessible, and visually polished.

---

# 26. Important Rule

**Design first. Code second. Verify third. Polish fourth.**

Never sacrifice usability for visual novelty.

Never sacrifice maintainability for visual polish.

Never sacrifice existing functionality for a redesign unless explicitly requested.

The final frontend should feel like it was designed by a thoughtful product team, not generated from a generic UI template.
