# Website Resolver v2.2

## Why this patch exists
A real test with `click my loan` and `https://web.clickmyloan.com/` exposed two identity gaps:

1. `click my loan` was only a fuzzy 92/100 match to the RBI snapshot name `ClickmyLoan`.
2. An official website URL did not trigger the Google Play public-listing scan.

## Fix
- App names now get an exact-equivalence compact normalization for spacing and punctuation.
- A dated alias registry maps selected official website domains to verified Google Play packages.
- For ClickMyLoan, `clickmyloan.com` maps to `com.habile.cloudbankin.clickmyloan`.
- The package is then used for the strongest RBI directory identity match and for Google Play metadata.

## Security boundary
The server does **not** make outbound HTTP requests to arbitrary user-supplied websites. That would introduce SSRF risk and unstable scraping. Unknown website domains remain unresolved; the app continues with name/developer/directory/ML checks and explains that no verified package mapping was found.

## Evidence
The alias registry records the Google Play source URL and verification date. It should be reviewed whenever the RBI snapshot or app identity changes.
