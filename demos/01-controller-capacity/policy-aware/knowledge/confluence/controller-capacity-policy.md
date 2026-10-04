# Controller capacity policy

Synthetic demonstration fixture. This is not a Data Honey customer record.

Document ID: controller-capacity-policy
Version: 1.0
Status: Approved
Owner: Scheduling Backend
Updated: 2026-09-15
Effective: 2026-09-15

## Capacity rules

For a LEGACY controller with valid supported firmware metadata, the maximum is 20 zones.
For a PRO controller with firmware earlier than 3.2.0, the maximum is 20 zones.
For a PRO controller with firmware 3.2.0 or later, the maximum is 50 zones.
The boundary is inclusive: PRO firmware exactly 3.2.0 is eligible for 50 zones.
Firmware versions are exactly three nonnegative numeric components separated by dots. Compare components numerically: 3.10.0 is later than 3.2.0. Whitespace, signs, suffixes, missing components, and unrecognized model names are invalid metadata.

## Metadata authority

The backend resolves controller model and firmware from the device registry using the request's controller ID. Request-supplied model, firmware, or capability overrides must be rejected. Missing firmware, malformed firmware, or unrecognized model metadata must produce an explicit capability-metadata validation error; do not silently infer capacity or fall back to a different model.

## Save behavior

Reject a request exceeding its device's capacity with HTTP 400 and `zone_limit_exceeded`. Validate before storing the schedule. A rejected request must neither allocate a saved schedule nor persist partial data. Successful saves return HTTP 201.

## Applicability

Version 1.0 is approved and effective for the demo tickets dated after 2026-09-15. Historical ticket completion and customer expectations do not override these rules. This policy defines capacity; it does not authorize or prescribe a firmware upgrade.
