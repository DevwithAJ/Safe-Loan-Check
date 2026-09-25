# Directory URL Normalization Fix v2.4

## Problem
Some rows in the RBI DLA export contain Google Play URLs without an `https://` scheme. The previous package-id parser ignored those stored URLs, so an exact package such as `org.altruist.BajajExperia` could fall back to fuzzy title matching and appear `Not listed`.

## Fix
- Package-id extraction now tolerates scheme-less Google Play URLs in stored directory data.
- User-entered URLs remain strict HTTPS-only through the normal validator.
- Current dated CSV URLs are normalized.
- Future import/refresh scripts normalize common scheme-less public URLs.
- Regression tests cover the Bajaj Finance package.

## Expected Bajaj identity result
`org.altruist.BajajExperia` -> `Bajaj Finance App` -> `BAJAJ FINANCE LTD.` -> `Listed`, match score `100/100`.

The final traffic-light verdict may still be Amber when independent public-listing or cost signals require review.
