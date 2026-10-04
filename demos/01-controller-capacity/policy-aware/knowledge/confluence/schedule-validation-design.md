# Schedule-save validation design

Synthetic demonstration fixture. This is not a Data Honey customer record.

Document ID: schedule-validation-design
Version: 1.0
Status: Approved
Owner: Scheduling Backend
Updated: 2026-09-16
Effective: 2026-09-16

## Request flow

The backend adapter accepts a controller ID and zone IDs, resolves the controller through the device registry, validates the schedule, and then saves it through the in-memory schedule repository. Successful saves return HTTP 201. Unknown controllers return HTTP 404. Request validation errors return HTTP 400.

## Authority and ownership

Scheduling Backend owns schedule-save validation and the backend service. The device registry supplies model and firmware facts. The approved controller capacity policy supplies the business requirements. Frontend validation helps the user construct a request; the backend independently enforces those requirements.

## Validation contract

The request permits only `controller_id` and `zones`. The controller ID must be a nonblank string. Zone IDs must be a nonempty list of positive integers, with no duplicates or boolean values. Reject unsupported fields, including model or firmware overrides. Validate capability metadata explicitly and do not save rejected requests.

## Storage boundary

This prototype uses an in-memory repository for demonstration. Its successful response shows that the current process stored a schedule; it does not establish durable storage, production deployment, or a released customer fix. Review the patch and verification results before accepting a change.
