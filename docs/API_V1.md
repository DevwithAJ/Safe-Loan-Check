# API v1

## GET `/api/v1/status`
Returns app version, directory snapshot metadata, ML model health, and public-metadata provider status.

## POST `/api/v1/check`

Header:

```text
Content-Type: application/json
```

Minimal body:

```json
{"app_name":"GeM Sahay"}
```

With Google Play evidence:

```json
{
  "app_name":"GeM Sahay",
  "app_reference_url":"https://play.google.com/store/apps/details?id=com.gemsahay.perfios"
}
```

With cost calculation:

```json
{
  "app_name":"Example Loan App",
  "calculate_cost":true,
  "loan_amount":10000,
  "processing_fee":500,
  "other_upfront_fees":0,
  "emi":1900,
  "tenure_months":6,
  "monthly_income":15000
}
```

The response keeps directory, ML/public-listing risk, cost and decision outputs separate and includes a responsible-use disclaimer.

The API is intended for first-party integration. Cross-origin access is not enabled by default.


With a supported official website:

```json
{
  "app_name":"click my loan",
  "app_reference_url":"https://web.clickmyloan.com/"
}
```

For backward compatibility, `play_store_url` is still accepted for direct Google Play links. Website URLs are never crawled by the server; only source-backed domains in the local alias registry can resolve to a Play package.
