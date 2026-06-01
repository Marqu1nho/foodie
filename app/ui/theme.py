"""
Mise visual theme for NiceGUI — extracted from Epicure Lab design prototype.
Warm direction: paper & spice palette with warm oklch hues.
"""

MISE_HEAD_HTML = '''<link rel="preconnect" href="https://fonts.googleapis.com" />
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
<link href="https://fonts.googleapis.com/css2?family=Spline+Sans:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;700&family=Newsreader:opsz,wght@6..72,400;6..72,600;6..72,700&display=swap" rel="stylesheet" />
<style>
:root {
  --sans: "Spline Sans", system-ui, sans-serif;
  --mono: "JetBrains Mono", ui-monospace, monospace;
  --display: "Newsreader", Georgia, serif;
  --bg: oklch(96% 0.013 80);
  --panel: oklch(99.2% 0.006 80);
  --field: oklch(97.6% 0.011 80);
  --line: oklch(89% 0.016 70);
  --ink: oklch(29% 0.022 55);
  --ink-soft: oklch(52% 0.022 55);
  --chip: oklch(93% 0.03 70);
  --chip-ink: oklch(36% 0.045 50);
  --chip-line: oklch(87% 0.03 60);
  --hover: oklch(94.5% 0.022 75);
  --track: oklch(90% 0.014 80);
  --edge: oklch(58% 0.05 50);
  --accent: oklch(57% 0.135 45);
  --accent-ink: oklch(98% 0.01 80);
  --accent-soft: oklch(76% 0.07 45);
  --anchor-ring: oklch(99.2% 0.006 80);
}
html, body {
  background: var(--bg);
  color: var(--ink);
  font-family: var(--sans);
  margin: 0;
}
</style>'''
