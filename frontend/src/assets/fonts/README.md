# Fonts (self-hosted)

Barlow and Barlow Semi Condensed (SIL Open Font License, see OFL.txt), loaded by `src/index.css` (Vite bundles them, so they work under any base path).
These are Latin subsets in WOFF format, made from the full TTF families in `../../../font-sources/`:

- barlow-400.woff, barlow-500.woff, barlow-600.woff
- barlow-semi-condensed-600.woff, barlow-semi-condensed-700.woff

To regenerate (needs `pip install fonttools`):
pyftsubset font-sources/Barlow/Barlow-Regular.ttf --unicodes="U+0000-024F,U+2000-206F,U+20AC,U+2122" --flavor=woff --layout-features="*" --output-file=src/assets/fonts/barlow-400.woff
