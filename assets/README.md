# assets

Static image assets used by report_generator.py, framework.py's
get_logo_data_uri(), and the Streamlit pages / email templates that call it.

- `bentley-logo-simplified-positive.png` — the official Bentley "Simplified
  Positive" lockup (wings + wordmark, dark-on-light). Used everywhere the
  background is white or light: report covers and page headers, the portal
  masthead, the rater/self-assessment form header.

- `bentley-logo-simplified-negative.png` — the "Simplified Negative" lockup
  (wings + wordmark, white-on-transparent). Used only where the background is
  dark: the email header banners (dark green for invitations, charcoal for
  reminders) - the positive mark would be nearly invisible there.

  Pass `negative=True` to `get_logo_data_uri()` to get this variant instead.

Both sourced from the real brand assets at
`Bentley Motors/Logos/Assets 2026-08-06/` (2026-08-06). These replaced an
earlier reverse-engineered wings-only mark that was never confirmed against
the actual brand book - don't reintroduce it.

The source SVGs (`Simplified Positive.svg` / `Simplified Negative.svg`, same
brand assets folder) are the vector originals, but python-docx can't embed
SVG into a .docx directly, so the PNGs are what's actually used. Both are
supplied at 300dpi, comfortably more resolution than needed at the sizes
used here.
