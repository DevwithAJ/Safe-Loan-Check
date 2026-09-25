# Data Collection Guide

## 1. DLA directory
Replace `data/dla_directory.csv` with a dated, traceable copy prepared from the RBI Digital Lending Apps Directory.
Keep at least:
- app_name
- developer_name
- regulated_entity
- source_date
- source_url
- is_demo (0 for real rows)

## 2. Risk-classifier dataset
Replace `data/app_risk_training.csv` with real, traceable public listing data.

Required feature columns:
- contacts_permission
- call_logs_permission
- sms_permission
- media_permission
- named_regulated_lender
- apr_disclosed
- developer_website_present
- physical_address_present
- company_email_domain
- app_age_days
- days_since_update
- installs_log10
- rating
- complaint_rate
- name_similarity
- label_risky
- label_source
- is_synthetic

Labelling rule:
- Verified: appears in the DLA directory.
- Risky: not in the directory AND at least one documented negative source.
- Excluded: neither group. Do not guess labels.

Important: directory status itself must NOT be used as a classifier feature.
