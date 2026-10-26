---
name: ICIA
colors:
  surface: '#faf8ff'
  surface-dim: '#d2d9f4'
  surface-bright: '#faf8ff'
  surface-container-lowest: '#ffffff'
  surface-container-low: '#f2f3ff'
  surface-container: '#eaedff'
  surface-container-high: '#e2e7ff'
  surface-container-highest: '#dae2fd'
  on-surface: '#131b2e'
  on-surface-variant: '#464555'
  inverse-surface: '#283044'
  inverse-on-surface: '#eef0ff'
  outline: '#777587'
  outline-variant: '#c7c4d8'
  surface-tint: '#4d44e3'
  primary: '#3525cd'
  on-primary: '#ffffff'
  primary-container: '#4f46e5'
  on-primary-container: '#dad7ff'
  inverse-primary: '#c3c0ff'
  secondary: '#00687a'
  on-secondary: '#ffffff'
  secondary-container: '#57dffe'
  on-secondary-container: '#006172'
  tertiary: '#005338'
  on-tertiary: '#ffffff'
  tertiary-container: '#006e4b'
  on-tertiary-container: '#67f4b7'
  error: '#ba1a1a'
  on-error: '#ffffff'
  error-container: '#ffdad6'
  on-error-container: '#93000a'
  primary-fixed: '#e2dfff'
  primary-fixed-dim: '#c3c0ff'
  on-primary-fixed: '#0f0069'
  on-primary-fixed-variant: '#3323cc'
  secondary-fixed: '#acedff'
  secondary-fixed-dim: '#4cd7f6'
  on-secondary-fixed: '#001f26'
  on-secondary-fixed-variant: '#004e5c'
  tertiary-fixed: '#6ffbbe'
  tertiary-fixed-dim: '#4edea3'
  on-tertiary-fixed: '#002113'
  on-tertiary-fixed-variant: '#005236'
  background: '#faf8ff'
  on-background: '#131b2e'
  surface-variant: '#dae2fd'
typography:
  display-lg:
    fontFamily: Outfit
    fontSize: 3rem
    fontWeight: '700'
    lineHeight: 3.5rem
    letterSpacing: -0.03em
  display-md:
    fontFamily: Outfit
    fontSize: 2.25rem
    fontWeight: '700'
    lineHeight: 2.75rem
    letterSpacing: -0.025em
  headline-lg:
    fontFamily: Outfit
    fontSize: 1.75rem
    fontWeight: '600'
    lineHeight: 2.25rem
    letterSpacing: -0.02em
  headline-md:
    fontFamily: Outfit
    fontSize: 1.375rem
    fontWeight: '600'
    lineHeight: 1.875rem
    letterSpacing: -0.015em
  headline-sm:
    fontFamily: Outfit
    fontSize: 1.125rem
    fontWeight: '600'
    lineHeight: 1.625rem
    letterSpacing: -0.01em
  body-lg:
    fontFamily: Inter
    fontSize: 1.125rem
    fontWeight: '400'
    lineHeight: 1.75rem
  body-md:
    fontFamily: Inter
    fontSize: 0.9375rem
    fontWeight: '400'
    lineHeight: 1.5rem
  body-sm:
    fontFamily: Inter
    fontSize: 0.8125rem
    fontWeight: '400'
    lineHeight: 1.25rem
  label-lg:
    fontFamily: Outfit
    fontSize: 1rem
    fontWeight: '600'
    lineHeight: 1.25rem
    letterSpacing: 0.01em
  label-md:
    fontFamily: Outfit
    fontSize: 0.875rem
    fontWeight: '600'
    lineHeight: 1.125rem
    letterSpacing: 0.015em
  label-sm:
    fontFamily: Outfit
    fontSize: 0.75rem
    fontWeight: '700'
    lineHeight: 1rem
    letterSpacing: 0.04em
  code-thermal:
    fontFamily: JetBrains Mono
    fontSize: 0.8125rem
    fontWeight: '500'
    lineHeight: 1.125rem
rounded:
  sm: 0.25rem
  DEFAULT: 0.5rem
  md: 0.75rem
  lg: 1rem
  xl: 1.5rem
  full: 9999px
spacing:
  gutter: 1.25rem
  gutter-desktop: 1.5rem
  margin: 1.25rem
  margin-desktop: 2rem
  space-xs: 0.25rem
  space-sm: 0.5rem
  space-md: 1rem
  space-lg: 1.5rem
  space-xl: 2.25rem
  space-2xl: 3rem
---

## Brand & Style
The product name is **ICIA**. Use it consistently in every interface surface: login, dashboard, window and tab titles, reports, thermal tickets, installer and desktop shortcut. Do not use previous names such as `RoboEnglish Academy OS` or `Kinetic Academy OS`.

The design system reflects a high-energy, forward-thinking 2026 educational hub specializing in robotics, computational thinking, and global language acquisition. It is engineered primarily for desktop administrative workstations, front-desk touch terminals, and high-frequency operational desks.

The brand personality balances:
- **Futuristic Competence:** Precision-engineered layouts, modular instrumentation, and crisp geometric data representation.
- **Approachable Optimism:** Radiant, accessible chromatic signals avoiding sterile enterprise drabness.
- **Operational Speed & Fluidity:** Optimized for sub-second visual triage and lightning-fast attendance processing (35 students checked in under 3 minutes) without cognitive fatigue.

The design movement combines **Modern High-Contrast Functionalism** with **Soft Tactile Tech**. It relies on bright, slate-anchored background plains, vibrant categorical color-coding, large hit targets with subtle physical press feedback, and crisp thermal preview panels that emulate physical receipts and workshop credentials.

## Colors
The color architecture delivers distinct visual channels designed for instant recognition across large desktop monitors and checkout-style touchscreens.

### Palette Architecture
- **Primary (Electric Indigo - `#4F46E5`):** Drives primary actions, system navigation, active attendance batches, and primary student profiles.
- **Secondary (Robotics Cyan - `#06B6D4`):** Represents STEM/Robotics curricula, active hardware modules, inventory sync, and live lab terminals.
- **Tertiary (Emerald Green - `#10B981`):** Indicates cleared balances, validated passes, confirmed attendance, and printable thermal tickets.
- **Alert Amber (`#F59E0B`):** Reserved for tuition balances, expiring bundles, and equipment checkouts pending return.
- **Coral Rose (`#F43F5E`):** Designates class cancellations, emergency medical notices, absences, and blocked check-ins.
- **Neutrals (Slate Tiers):**
  - Base Background: Canvas `#F8FAFC`
  - Surface Elevation: Crisp White `#FFFFFF`
  - Border & Dividers: Muted Slate `#E2E8F0`
  - Secondary Infill: Cool Slate `#F1F5F9`
  - Body Text: Slate 700 `#334155`
  - High-Contrast Headlines & Primary Tokens: Slate 900 `#0F172A`

### Color Usage Rules
- Avoid plain gray backgrounds; all neutral surfaces carry a precise slate tint to prevent glare under bright academy lighting.
- Semantic indicators (Amber, Rose, Emerald) must never appear purely as decorative fills; they always convey financial, status, or attendance metadata.
- All interactive color fills must maintain an APCA/WCAG contrast ratio greater than 4.5:1 against their corresponding text.

## Typography
The system employs a dual-typeface strategy to combine technical authority with legible transaction ergonomics:
- **Headlines & Interface Labels (Outfit):** Geometric, precise, and charismatic. Outfit delivers strong tabular rhythm for badges, student names, and action buttons.
- **Body Text & Tabular Data (Inter):** Highly legible, neutral workhorse engineered for dense grids, student directories, logs, and fee tables.
- **Receipts & Thermal Pass Tokens (JetBrains Mono):** Applied exclusively within physical print ticket emulators, barcode labels, and RFID identifier tags.

### Sizing and Hierarchy Principles
- Counter and check-in rosters use `label-lg` and `headline-sm` with increased tracking to ensure legibility from a 2-foot desk standing distance.
- Numeric balances, student age tags, and time indicators use tabular numerals (`tnum`) across all styles to prevent layout shifting during real-time batch check-ins.

## Layout & Spacing
The layout model is optimized for desktop and touch-screen operations (1280px to 2560px displays) using a high-density, multi-column fluid workspace.

### Grid & Structure
- **Root Shell:** Fixed left persistent command rail (80px collapsed / 240px expanded), an interactive primary workspace, and a right-anchored "Thermal Action & Queue" panel (340px to 400px width).
- **Primary Grid:** 12-column adaptive layout with `1.5rem` gutters on desktop displays.
- **Rapid Check-in Roster:** 3-to-4 column responsive card grid allowing front-desk personnel to view at least 16 student blocks simultaneously above the fold.

### Spacing Strategy
- Compact internal component gaps (`space-xs` to `space-sm`) keep student attributes closely bound to their targets.
- Generous external component boundaries (`space-md` to `space-lg`) prevent accidental touch mis-clicks during rapid queue processing.

## Elevation & Depth
Depth in this system avoids heavy, muddy drop shadows in favor of crisp, layered modern dimensionality.

### Ambient Luminescence & Layering
1. **Level 0 (App Canvas):** Soft neutral fill (`#F8FAFC`) with zero elevation.
2. **Level 1 (Cards, Modules, Rosters):** Pure white background (`#FFFFFF`) with a micro-border of `1px solid #E2E8F0` and an ambient glow:
   `0 1px 3px rgba(15, 23, 42, 0.04), 0 4px 12px -2px rgba(15, 23, 42, 0.03)`.
3. **Level 2 (Interactive Floating Actions & Hovered Student Cards):** Lifted with colored tinting:
   `0 10px 25px -5px rgba(79, 70, 229, 0.1), 0 8px 10px -6px rgba(15, 23, 42, 0.06)`.
4. **Level 3 (Modals, Student Thermal Pass Preview Drawer):** High-focus overlay using:
   `0 20px 40px -15px rgba(15, 23, 42, 0.14)`.

### Tactile Feedback
Interactive buttons and rapid check-in targets feature a physical `1.5px` inset border or dynamic Y-axis depression (`transform: translateY(1.5px)`) upon active trigger, providing clear haptic and visual confirmation on high-speed desktop clicks and touch displays.

## Shapes
The system relies on a hyper-friendly, modern 2026 aesthetic characterized by generous radii that soften technical robotics data and invite fast physical interactions.

### Shape Scales
- **Standard Controls & Badges (0.5rem - `rounded-md`):** Used for micro-pills, code snippets, and form inputs.
- **Interactive Tiles & Student Row Anchors (1rem - `rounded-lg`):** Standard interactive surfaces, quick action grids, and input clusters.
- **Primary Module Containers & Cards (1.5rem - `rounded-xl`):** Attendance roster blocks, hardware tracker pods, and live camera feeds.
- **Thermal Print Previews:** Employs crisp 0.75rem rounded corners combined with a saw-toothed or dashed decorative cutout edge along bottom receipts to simulate physical ticketing.
- **Status Pills:** Fully rounded capsule/pill shape (`rounded-full`) for instant glanceability.

## Components

### 1. Rapid Check-In Student Cards
- **Architecture:** Compact card containing a 48px avatar/badge, student full name (`label-lg`), balance status pill, and one-tap presence triggers.
- **Action State:** A single large tactile button on the card:
  - *Unchecked:* Slate outline (`#E2E8F0`), secondary hover glow.
  - *Checked-in:* Transitions instantaneously to Solid Emerald (`#10B981`) with a white checkmark icon, triggering the thermal queue counter.
- **Dimensions:** Min-height 84px to support fast finger or stylus tapping without miss-clicks.

### 2. Status Pills
- **Paid / Cleared:** Soft Emerald background (`#ECFDF5`), Emerald text (`#047857`), solid micro-dot.
- **Debt / Pending Tuition:** Soft Amber background (`#FFFBEB`), Amber text (`#B45309`), warning triangle icon.
- **Canceled / Inactive:** Soft Coral background (`#FFF1F2`), Rose text (`#BE123C`).
- **Robotics Track:** Soft Cyan background (`#ECFEFF`), Cyan text (`#0E7490`).
- **English Track:** Soft Indigo background (`#EEF2FF`), Indigo text (`#4338CA`).

### 3. Thermal Ticket Preview Card
- **Visual Design:** Monospace and Outfit hybrid styled as an authentic thermal terminal ticket.
- **Styling:** White surface, dashed horizontal divider lines (`#CBD5E1`), high-contrast QR code placeholder, student PIN, timestamp, class module name, and seat assignment.
- **Utility:** Displays a direct "Print & Dispense" shortcut with persistent keyboard access (e.g., `Enter` or `Spacebar` for sub-second printing).

### 4. Interactive Buttons
- **Primary (Electric Indigo):** `#4F46E5` fill, pure white text, subtle bottom-lip shadow (`0 2px 0 #3730A3`). When clicked, it compresses downwards by 1.5px.
- **Rapid Action (Cyan / Emerald):** Applied to fast-action academy workflows like "Batch Complete" or "Dispense Card".
- **Ghost / Utility:** `#F1F5F9` neutral slate button with `#0F172A` text; active state darkens to `#E2E8F0`.

### 5. Input & Filter Fields
- Height of 48px minimum for rapid touch focus.
- Slate border (`#E2E8F0`) transitioning to a 2px Indigo glow ring (`#4F46E5` at 30% alpha) on focus.
- Integrated barcode/RFID scanner listeners: automatically highlights green when receiving raw input from peripheral USB/Bluetooth hardware scanners.

### 6. Lists & Rosters
- Alternating subtle rows (`#FFFFFF` to `#F8FAFC`).
- Sticky headers with integrated category filters (e.g., *Robotics Lab A*, *ESL Level 2*, *Debtors Only*).
- Left-aligned multi-select checkboxes sized at 22px × 22px for rapid batch clearing.