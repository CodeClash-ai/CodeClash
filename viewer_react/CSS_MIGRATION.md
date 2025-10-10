# CSS Migration Summary

This document summarizes the CSS styling migration from the old Flask-based viewer to the new React-based viewer.

## Overview

All styling from the old viewer has been ported to match the professional dark theme with bright green (`#00ff88`) accents. The CSS has been simplified and organized into reusable component-based styles.

## Color Scheme

### Primary Colors
- **Background Primary**: `#000000` (Pure black)
- **Background Secondary**: `#111111` (Dark gray)
- **Background Tertiary**: `#222222` (Lighter gray)
- **Text Primary**: `#ffffff` (White)
- **Text Secondary**: `#cccccc` (Light gray)
- **Text Muted**: `#888888` (Medium gray)
- **Border Color**: `#333333` (Dark border)

### Accent Colors
- **Accent/Primary**: `#00ff88` (Bright green)
- **Accent Hover**: `#00cc66` (Darker green)
- **Success**: `#00ff88` (Same as accent)
- **Warning**: `#f711ff` (Magenta)
- **Danger/Error**: `#ff4444` (Red)
- **Neon Red**: `#ff1188` (Bright red for errors)

### Message Role Colors
- **System**: `#ffaa00` (Orange)
- **User**: `#00ff88` (Green)
- **Assistant**: `#00aaff` (Blue)

## File Structure

### Global Styles
1. **`index.css`** - CSS reset and base HTML/body styles
2. **`App.css`** - Core application styles, CSS variables, utility classes

### Component Styles
1. **`GamePicker.css`** - Game selection table and filtering UI
2. **`GameViewer.css`** - Main game viewer layout
3. **`Header.css`** - Header with navigation and controls
4. **`Overview.css`** - Overview section with agents and results
5. **`Analysis.css`** - Analysis section with charts and matrices
6. **`RoundsList.css`** - Rounds listing and display
7. **`TrajectoryViewer.css`** - Trajectory display with messages
8. **`Storage.css`** - Storage/path management UI
9. **`Readme.css`** - Readme editor component
10. **`ScoresChart.css`** - Score visualization charts
11. **`FloatingToc.css`** - Floating table of contents
12. **`HelpModal.css`** - Keyboard shortcuts help modal

## Key Design Patterns

### 1. Consistent Color Usage
- All text uses high-contrast colors on black background
- Accent color (`#00ff88`) used consistently for:
  - Interactive elements
  - Headers and titles
  - Active states
  - Success indicators

### 2. Interactive Elements
- **Buttons**: Black text (`#000000`) on bright green (`#00ff88`)
- **Hover states**: Darker green (`#00cc66`) with slight transform
- **Disabled states**: 50% opacity with no-cursor
- **Focus states**: 2px green outline with offset

### 3. Card Components
- Background: `var(--bg-secondary)`
- Border: `1px solid var(--border-color)`
- Border radius: `0.5rem`
- Box shadow for depth
- Hover effect: subtle transform up

### 4. Foldout/Accordion Components
- Summary with tertiary background
- Hover: Full green background with black text
- Smooth transitions for expand/collapse
- Consistent padding and spacing

### 5. Tables
- Sticky headers with tertiary background
- Row hover: Tertiary background
- Cell padding: `0.75rem 1rem`
- Text: Always white for visibility
- Border: Bottom border on all rows except last

### 6. Code Blocks
- Background: `var(--code-bg)` (`#0a0a0a`)
- Monospace font: "SF Mono", Monaco, "Cascadia Code", etc.
- Border: `1px solid var(--border-color)`
- Pre-wrap for long lines
- Scrollable containers with custom scrollbar

### 7. Scrollbars (Webkit)
- Width/Height: `8px`
- Track: Dark background
- Thumb: Muted gray, bright green on hover
- Border radius: `4px`

### 8. Badges and Tags
- Background: Bright green or success color
- Text: Black (`#000000`) for contrast
- Font weight: `700` (Bold)
- Border radius: `0.75rem` for pills
- Small padding: `0.125rem 0.375rem`

### 9. Status Indicators
- **Submitted**: Green (`#00ff88`)
- **Failed/Timeout**: Neon red (`#ff1188`)
- **Success**: Green
- **Warning**: Magenta (`#f711ff`)

## Reusable CSS Classes

### Spacing Utilities
- `.mt-1`, `.mt-2`, `.mt-3` - Margin top
- `.mb-1`, `.mb-2`, `.mb-3` - Margin bottom

### Flexbox Utilities
- `.flex` - Display flex
- `.flex-col` - Flex column direction
- `.gap-1`, `.gap-2`, `.gap-3` - Gap spacing
- `.items-center` - Align items center
- `.justify-between` - Space between
- `.justify-center` - Center justify

### Grid Utilities
- `.grid` - Display grid
- `.grid-cols-2`, `.grid-cols-3` - Column templates
- `.grid-cols-auto` - Auto-fit grid

### Text Utilities
- `.text-muted` - Muted gray text
- `.text-success` - Success green text
- `.text-warning` - Warning magenta text
- `.text-error` - Error red text

### Component Classes
- `.card` - Card container
- `.section` - Page section
- `.badge` - Badge/pill component
- `.code-block` - Code display
- `.loading`, `.loading-small` - Loading states
- `.error`, `.error-small` - Error states

## Responsive Design

### Breakpoints
- Mobile: `max-width: 768px`
- Small mobile: `max-width: 480px`

### Mobile Adaptations
- Headers: Stack vertically, center align
- Tables: Reduced columns, hide non-essential
- Font sizes: Slightly smaller
- Padding: Reduced spacing
- Grid: Single column layouts
- TOC: Adjusted positioning

## Animation & Transitions

### Standard Transitions
- Duration: `0.2s` for most interactions
- Easing: `cubic-bezier(0.4, 0, 0.2, 1)`
- Properties: `all` or specific (color, background-color, border-color)

### Transform Effects
- Buttons: `-1px` translateY on hover
- Cards: `-2px` translateY on hover
- Scale: `1.05` to `1.1` for small interactive elements

### Loading Spinner
- Border animation rotating 360°
- Duration: `1s linear infinite`
- Border: Top color is accent, others are transparent accent

## Simplifications Made

1. **Consolidated Variables**: Used CSS custom properties throughout
2. **Removed Redundancy**: Eliminated duplicate styles
3. **Component-Based**: Split styles by component for maintainability
4. **Utility Classes**: Created reusable utility classes
5. **Consistent Naming**: Used semantic class names
6. **Simplified Selectors**: Avoided overly specific selectors
7. **Modern CSS**: Used flexbox and grid instead of floats
8. **Better Organization**: Logical grouping of related styles

## Key Improvements

1. **Better Maintainability**: Component-based CSS is easier to update
2. **Consistency**: Centralized color variables ensure uniform appearance
3. **Performance**: Removed unused styles and optimized selectors
4. **Accessibility**: Better focus states and keyboard navigation
5. **Responsiveness**: Mobile-first approach with clear breakpoints
6. **Dark Mode Native**: Built specifically for dark theme
7. **Type Safety**: Can be integrated with CSS-in-JS if needed

## Migration Checklist

✅ Color scheme and variables
✅ Base HTML/body styles
✅ Typography and fonts
✅ Buttons and interactive elements
✅ Cards and containers
✅ Tables and grids
✅ Forms and inputs
✅ Foldouts and accordions
✅ Modals and overlays
✅ Code blocks and monospace
✅ Badges and tags
✅ Status indicators
✅ Loading and error states
✅ Scrollbars
✅ Responsive design
✅ Animations and transitions
✅ Utility classes
✅ Component-specific styles

## Browser Support

The CSS uses modern features supported in:
- Chrome/Edge 88+
- Firefox 78+
- Safari 14+

### Features Used
- CSS Custom Properties (Variables)
- Flexbox
- Grid Layout
- Transform and Transitions
- Border Radius
- Box Shadow
- Backdrop Filter
- Sticky Positioning
- Webkit Scrollbar Styling

## Testing Recommendations

1. Test in all major browsers (Chrome, Firefox, Safari, Edge)
2. Test responsive layouts on various screen sizes
3. Test keyboard navigation and focus states
4. Verify color contrast for accessibility
5. Test with screen readers
6. Verify dark theme in different lighting conditions
7. Test hover states on touch devices
8. Check loading and error states
9. Verify table scrolling and overflow
10. Test modal and overlay interactions

## Future Enhancements

Potential improvements for future iterations:

1. **CSS-in-JS**: Consider styled-components or emotion for type safety
2. **CSS Modules**: For better scoping and collision prevention
3. **Theme Switching**: Add light mode support
4. **CSS Variables**: Expand variable system for more flexibility
5. **Animation Library**: Consider framer-motion for complex animations
6. **Design Tokens**: Implement design token system
7. **CSS Grid Templates**: More sophisticated grid layouts
8. **Print Styles**: Add print-friendly CSS
9. **Reduced Motion**: Respect prefers-reduced-motion
10. **High Contrast**: Support for high-contrast modes
