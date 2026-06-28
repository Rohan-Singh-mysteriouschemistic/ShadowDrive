# ShadowDrive Mobile Responsive Design Guide

## Overview

This document outlines the mobile-responsive improvements made to the ShadowDrive UI. The implementation follows a mobile-first approach with Tailwind CSS breakpoints and custom utilities.

## Key Changes

### 1. **CSS Enhancements** (`src/index.css`)

#### New Spacing Tokens
- `--spacing-gutter-mobile`: 16px (mobile-optimized spacing)
- `--spacing-page-padding-mobile`: 16px
- `--spacing-page-padding-tablet`: 24px
- `--spacing-page-padding-desktop`: 48px
- `--spacing-header-height-mobile`: 56px
- `--spacing-header-height-desktop`: 80px

#### Responsive Utilities
- `.page-content`: Responsive padding based on screen size
- `.header-actions`: Flexible action button layout with wrapping
- `.table-row-mobile`: Mobile-optimized table row display
- `.table-cell-label`: Label styling for mobile table cells

#### Touch-Friendly Enhancements
- Minimum touch target size: 48px (3rem) for all interactive elements
- Applied via `@media (hover: none) and (pointer: coarse)` for touch devices

#### Mobile Drawer Animations
- `.drawer-enter`: Slide-in animation from left
- `.drawer-exit`: Slide-out animation to left

### 2. **Page Header Component** (`src/components/PageHeaderMobile.tsx`)

Enhanced header component with:
- Responsive height: 56px on mobile, 80px on desktop
- Responsive padding: 16px on mobile, 48px on desktop
- Truncated title with proper overflow handling
- Menu toggle button (mobile-only)
- Flexible action button layout

**Usage:**
```tsx
<PageHeaderMobile
  icon="home"
  title="Vault"
  actions={<Button>Upload</Button>}
  onMenuToggle={() => setMenuOpen(true)}
/>
```

### 3. **Mobile Navigation Drawer** (`src/components/MobileNavDrawer.tsx`)

Full-screen navigation drawer with:
- Slide-in/out animations
- Backdrop overlay with blur effect
- Logo and branding
- Menu items with active state indicators
- Storage usage display
- Logout button
- Automatic body scroll lock when open

**Features:**
- Responsive to all navigation items
- Badge support for conflict counts
- Touch-friendly spacing
- Smooth transitions

**Usage:**
```tsx
<MobileNavDrawer
  isOpen={mobileMenuOpen}
  onClose={() => setMobileMenuOpen(false)}
  menuItems={menuItems}
  systemItems={systemItems}
  currentPath={location.pathname}
  storage={storage}
  onLogout={() => setShowConfirmLogout(true)}
/>
```

### 4. **Responsive Table Component** (`src/components/ResponsiveTable.tsx`)

Reusable component for displaying tabular data on both desktop and mobile:
- Desktop: Grid-based table layout
- Mobile: Card-based layout with label-value pairs
- Customizable columns with alignment options
- Loading and empty states

**Usage:**
```tsx
<ResponsiveTable
  columns={[
    { key: 'name', label: 'File Name', width: '40%' },
    { key: 'size', label: 'Size', align: 'right' },
    { key: 'date', label: 'Modified', mobileHidden: false },
  ]}
  rows={files}
  renderCell={(row, col) => row[col.key]}
  onRowClick={(row) => handleSelect(row)}
/>
```

### 5. **Dashboard Layout Updates** (`src/layouts/DashboardLayout.tsx`)

- Mobile header with working menu toggle
- Integrated MobileNavDrawer component
- Responsive modal buttons (flex-col on mobile, flex-row on desktop)
- Reduced logo size on mobile (20px vs 32px)
- Optimized header height

### 6. **Page-Specific Updates**

#### FileExplorer.tsx
- **Desktop**: Grid-based table with 12 columns
- **Mobile**: Card-based layout with file icon, name, size, date, and action buttons
- Responsive padding using `.page-content` utility
- Touch-friendly action buttons

#### VersionHistory.tsx
- **Desktop**: Side-by-side layout with summary card and version list
- **Mobile**: Stacked layout with full-width summary and card-based version list
- Responsive gap spacing
- Optimized padding for mobile

## Responsive Breakpoints

| Breakpoint | Width | Usage |
|---|---|---|
| Mobile | < 768px | Phone devices |
| Tablet | 768px - 1023px | Tablet devices |
| Desktop | ≥ 1024px | Desktop computers |

## Touch Optimization

All interactive elements on touch devices have:
- Minimum 48px × 48px hit target
- 8px padding around buttons
- No hover states (replaced with active states)
- Larger text for readability

## Color & Contrast

All mobile UI elements maintain:
- WCAG AA contrast ratios
- Consistent color scheme from design tokens
- Glass-morphism effects preserved
- Glow effects on primary elements

## Performance Considerations

- CSS media queries are optimized
- No JavaScript required for responsive behavior
- Smooth animations use GPU acceleration
- Drawer uses `transform` for optimal performance

## Testing Checklist

- [ ] Test on iPhone 12/13 (390px)
- [ ] Test on iPhone 14 Pro Max (430px)
- [ ] Test on Samsung Galaxy S21 (360px)
- [ ] Test on iPad (768px)
- [ ] Test on iPad Pro (1024px)
- [ ] Test landscape orientation
- [ ] Test touch interactions
- [ ] Test drawer open/close
- [ ] Test modal responsiveness
- [ ] Test table scrolling on mobile

## Browser Support

- iOS Safari 12+
- Chrome Android 90+
- Firefox Android 88+
- Samsung Internet 14+

## Future Enhancements

1. Add swipe gestures for drawer open/close
2. Implement bottom sheet navigation for mobile
3. Add responsive font scaling
4. Optimize images for mobile
5. Add PWA support with offline caching
6. Implement gesture-based file actions
7. Add haptic feedback for touch interactions
8. Optimize for foldable devices

## Migration Guide

### Updating Existing Pages

To make an existing page mobile-responsive:

1. **Replace padding:**
   ```tsx
   // Before
   <div className="p-margin-desktop">
   
   // After
   <div className="page-content">
   ```

2. **Make tables responsive:**
   ```tsx
   // Before
   <div className="grid grid-cols-12">
   
   // After
   <div className="hidden md:grid grid-cols-12">
   {/* Add mobile card view below */}
   <div className="md:hidden">
   ```

3. **Update modals:**
   ```tsx
   // Before
   <div className="flex gap-4">
   
   // After
   <div className="flex flex-col sm:flex-row gap-4">
   ```

4. **Add header menu toggle:**
   ```tsx
   <PageHeaderMobile
     onMenuToggle={() => setMenuOpen(true)}
   />
   ```

## Troubleshooting

### Drawer not closing on navigation
- Ensure `onClose()` is called in navigation handlers
- Check z-index stacking context

### Touch targets too small
- Use `min-h-12 min-w-12` classes on buttons
- Increase padding on interactive elements

### Text overflow on mobile
- Use `truncate` class for single-line text
- Use `line-clamp-*` for multi-line text
- Reduce font size with `sm:text-*` utilities

### Layout shifting on scroll
- Use `overflow-hidden` on body when drawer is open
- Ensure fixed positioning is correct

## Resources

- [Tailwind CSS Responsive Design](https://tailwindcss.com/docs/responsive-design)
- [Material Design Mobile Guidelines](https://material.io/design/platform-guidance/android-bars.html)
- [WCAG Mobile Accessibility](https://www.w3.org/WAI/mobile/)
