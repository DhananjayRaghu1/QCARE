# Controller Zone Limits

Synthetic demonstration fixture. This is not a DataHoney customer record.

Product: Irrigation Scheduler

Legacy Controller
Maximum zones: 20

Pro Controller
Maximum zones: 50

Schedule validation must use the capabilities of the selected controller model.
A single global zone limit must not be applied across all controller models.

These limits apply when a schedule is created through the Scheduling API as
well as in the frontend editor. At the boundary, Pro schedules with 50 zones
are valid; 51 zones are invalid. Legacy schedules with 20 zones are valid;
21 zones are invalid.

The backend capability table is in app/controller_capabilities.py.
This document does not establish customer-specific overrides or firmware
exceptions; confirm those separately if a report needs them.

