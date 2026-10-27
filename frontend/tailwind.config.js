import frappeUIPreset, { content as frappeUIContent } from 'frappe-ui/tailwind'

// Tokens from docs/design/README.md
export default {
  presets: [frappeUIPreset],
  content: ['./index.html', './src/**/*.{vue,js,ts}', ...frappeUIContent],
  theme: {
    extend: {
      colors: {
        hasr: {
          ink: '#171717',
          secondary: '#525252',
          muted: '#6B6B6B',
          surface: '#FFFFFF',
          surface2: '#F3F3F3',
          line: '#EDEDED',
          yellow: '#F5B800',
          success: '#15803D',
          'success-bg': '#E8F7EE',
          warning: '#A14A05',
          'warning-bg': '#FFF3E0',
          danger: '#B42318',
          'danger-bg': '#FDECEC',
          info: '#0B5CAD',
          'info-bg': '#EEF4FC',
        },
      },
      fontFamily: {
        hasr: ['Inter', 'IBM Plex Sans Arabic', 'system-ui', 'sans-serif'],
      },
      borderRadius: { hasr: '8px', sheet: '16px', tile: '12px' },
      minHeight: { tap: '44px' },
      minWidth: { tap: '44px' },
    },
  },
  plugins: [],
}
