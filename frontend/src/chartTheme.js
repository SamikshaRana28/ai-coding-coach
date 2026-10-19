// Dark-friendly colors for Recharts. Import from here instead of hard-coding colors in a page.
export const CHART = {
  primary: '#7c83ff',
  secondary: '#22d3ee',
  success: '#34d399',
  warning: '#fbbf24',
  danger: '#f87171',
  grid: '#26314a',
  track: '#26314a',
  axis: '#8a94ad',
  axisProps: { stroke: '#34415f', tick: { fill: '#8a94ad', fontSize: 12 } },
  tooltip: {
    contentStyle: { background: '#1a2234', border: '1px solid #26314a', borderRadius: 8, color: '#e6e9f2' },
    labelStyle: { color: '#e6e9f2' },
    itemStyle: { color: '#e6e9f2' },
    cursor: { fill: 'rgba(124,131,255,0.12)' },
  },
  legend: { wrapperStyle: { color: '#c4cbdc' } },
}
