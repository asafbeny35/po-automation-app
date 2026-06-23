# Mobile management app redesign research

Date: 2026-06-19

This redesign direction is based on product patterns from successful complex management apps and Apple’s iOS guidance.

## Sources

1. Apple Human Interface Guidelines
   - Tab bars: https://developer.apple.com/design/human-interface-guidelines/tab-bars
   - Navigation and search: https://developer.apple.com/design/human-interface-guidelines/navigation-and-search
2. Linear Mobile
   - https://linear.app/mobile
3. ClickUp mobile
   - https://help.clickup.com/hc/en-us/articles/15145935126679-Intro-to-the-mobile-app
4. Notion mobile
   - https://www.notion.com/help/notion-for-mobile
5. Salesforce mobile app
   - https://help.salesforce.com/s/articleView?id=xcloud.salesforce_app.htm&language=en_US&type=5
   - https://help.salesforce.com/s/articleView?id=xcloud.salesforce_app_mobile_home.htm&language=en_US&type=5
6. monday.com mobile
   - https://support.monday.com/hc/en-us/articles/360015740220-Mobile-app-board-views

## Key findings

### 1. Mobile must not be desktop squeezed into a phone

Linear explicitly positions mobile as an experience for “away from keyboard” workflows. ClickUp also documents mobile as a place for quick action while noting that some features are intentionally not brought to mobile because they are too large for the small screen.

Implication for PO:

- the app should prioritize quick flows
- create order
- upload invoice
- send delivery confirmation
- update payment status
- inspect customer docs

Heavy administrative depth can exist, but it should open progressively and not dominate the main navigation.

### 2. Five primary navigation areas are enough

Apple’s tab bar guidance supports using tab bars for top-level sections. Salesforce mobile also emphasizes configurable navigation and mobile home as a primary entrypoint.

Implication for PO:

- keep only 5 fixed bottom tabs
- Home / Center
- Orders
- Payments
- Finance
- Customers

Everything else should move under More or into contextual sheets and drill-ins.

### 3. One mobile home should centralize attention

ClickUp’s mobile documentation describes Home as the centralized place to work, and Linear uses Inbox/notifications as the attention router.

Implication for PO:

- the landing screen should not be a large decorative dashboard
- it should be an operational inbox with:
  - exceptions
  - pending delivery confirmations
  - recent uploads waiting for parse approval
  - quick create actions

### 4. Lists beat giant cards for operational density

Notion mobile collapses complexity on mobile and removes desktop-only structural affordances such as columns and hover behavior. monday.com leans on alternate views rather than one overloaded surface.

Implication for PO:

- reduce tall hero blocks
- reduce giant summary cards
- use compact list rows with:
  - title
  - 1 to 2 metadata lines
  - status badge
  - one primary action

### 5. Use sheets for depth, not full-screen detours

The apps above consistently use compact overlays, drill-ins, and contextual action surfaces instead of sending the user through long full-screen forms for every detail.

Implication for PO:

- invoice parse review should open in a bottom sheet
- customer recent documents should open in a sheet
- order row details should open in a sheet
- payroll package actions should open in a sheet

### 6. The iPhone app should feel native in interaction, not just in technology

Native feel comes from navigation, density, motion, and control choice, not just from using SwiftUI/UIKit.

Implication for PO:

- bottom tab navigation instead of web-like chips
- segmented controls where mutually exclusive views exist
- grouped lists
- immediate transitions
- no full loading screen on every sub-tab switch
- RTL must be first-class in every component

## What changed in the redesign concept

The prototype was rebuilt around these findings:

- from a presentation-like shell around a single phone to a research-backed gallery of actual mobile screens
- from big dashboard cards to compact operational rows
- from many top-level areas to five core tabs
- from desktop-parity thinking to mobile-first operational flows
- from decorative structure to task-oriented surfaces
