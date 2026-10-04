# Recorded workflow: rehearsal-1

Synthetic fixtures. Model traces and test results are actual executions.
Source checks establish provenance; human review of claim support remains pending.

## investigate — AG-1423 — success

Run: investigate-20261004T174312-46295c57 · Model: claude-sonnet-5-5 · Time: 36.37s

# Decision packet: AG-1423

Source provenance and read coverage are mechanically checked. Claim support requires human review. See run metadata for the actual model and run status.

**Device:** DEV-101; model PRO; firmware 3.4.0. [reg101](#reg101)

**Policy (established):** Approved controller-capacity-policy v1.0 (effective 2026-09-15, owner Scheduling Backend, applies to demo tickets dated after that; AG-1423 is dated 2026-10-02). PRO firmware 3.2.0 or later allows 50 zones (inclusive boundary); PRO below 3.2.0 and LEGACY allow 20. Capacity is resolved from the registry, not the request. Over-capacity saves must return 400 zone_limit_exceeded. DEV-101 (PRO 3.4.0) is eligible for 50 zones, so a 30-zone save is expected to succeed with 201. [polMeta](#polmeta) [polRules](#polrules) [polAuth](#polauth) [polSave](#polsave) [polApply](#polapply) [reg101](#reg101)

**Diagnosis (investigate_mismatch):** Observation: the ticket reports a 400 zone_limit_exceeded for 30 zones on DEV-101, and success for 20. Policy and registry say 30 zones should be accepted. The code explains the report: validate_zones uses a fixed MAX_ZONES = 20, and the service maps that message to zone_limit_exceeded. The code never uses model or firmware to choose a limit, though it does check that they are well-formed. Hypothesis (strong, not executed): backend enforcement was never updated to the approved policy, so any 21 to 50 zone request for an eligible PRO controller is wrongly rejected. The reproduction has not been run. This is a mismatch rather than an expected rejection. [ticket](#ticket) [polRules](#polrules) [polSave](#polsave) [reg101](#reg101) [val](#val) [svc](#svc)

## Starting files

- `app/schedule_validator.py:6-24` — Fixed MAX_ZONES = 20 is applied to every device after metadata validation; this is where the capacity decision belongs. [val](#val)

- `app/schedule_service.py:24-30` — Fetches the registry record, calls the validator, and maps the 'Controller supports at most' message prefix to the zone_limit_exceeded code. Any change to the message text would silently alter the code. [svc](#svc)

**Execution path:** create_schedule requires exactly controller_id and zones, which rejects overrides. It looks up DEV-101 in the registry (PRO, 3.4.0) and calls validate_zones(zones, device). The validator accepts the model and firmware as well-formed, then checks the zone list shape and duplicates. It then compares len(zones) to the constant 20. 30 zones fail and return the 'Controller supports at most 20 zones' string, which the service converts to HTTP 400 zone_limit_exceeded before any save. 20 zones pass and return 201. [svc](#svc) [val](#val) [reg101](#reg101)

## History and ownership

- AG-981 (Closed, Frontend Scheduling, 2026-09-18) delivered the editor selecting up to 50 zones for eligible Pro controllers. This is consistent with the editor allowing 30 selections. It states that frontend completion does not establish that backend paths enforce the expanded policy. [hist981](#hist981)

- Unknown: code-change history for the validator is not available in the captured evidence.

**Owner:** Scheduling Backend owns schedule-save validation and the backend service, per the approved design and policy documents. Frontend Scheduling owns the editor. The ticket itself is owned by Support Triage. Individual assignees are Unknown. [design](#design) [polMeta](#polmeta) [hist981Resp](#hist981resp) [ticket](#ticket)

**Next action:** A backend software change is justified, pending confirmation. Smallest verification: through the backend adapter, submit DEV-101 with zones 1 to 30 and then 1 to 20, recording status and code. Expect 201 for both under policy; the current code is expected to give 400 zone_limit_exceeded for 30. Scheduling Backend would then make the validator derive capacity from the registry's model and firmware. Boundary cases to check are PRO 3.2.0 (50) and PRO 3.1.0 (20, as for DEV-102). Also confirm 51 zones still returns 400 and that rejected requests save nothing. This does not propose a firmware upgrade or a workaround. [polRules](#polrules) [polSave](#polsave) [polApply](#polapply) [val](#val)

## Open questions

- The reproduction was not executed (execution is not allowed), so the 400 response is inferred from code and not observed.

- Whether tests exist for this behavior is unknown; tests/ was not inspected.

- Individual assignee or owner of the validator and the code-change history are unavailable.

- No approved workaround or firmware-upgrade procedure exists in the evidence.

- Whether the frontend sends the request through the same backend path as the adapter is not established.

## Captured citations

### reg101

`app/devices.json:2-5` (registry); SHA-256 `cc8b7f966610ce03ee8ba89d4733948fb98035a7ed4a8c897988d90799943c5c`.

```text
  "DEV-101": {
    "model": "PRO",
    "firmware": "3.4.0"
  },
```

### ticket

`knowledge/jira/AG-1423.md:11-21` (knowledge); SHA-256 `97ae812e973335c64c587a93d06bece10ee1d24371010164e20ff456a03dbfda`.

```text
## Reported behavior

The customer reports that saving 30 zones on controller DEV-101 returns HTTP 400 with `zone_limit_exceeded`. Saving 20 zones on the same controller succeeds. The browser editor allows the customer to select the 30 zones before saving.

## Reproduction

Use `controller_id: DEV-101` and zone IDs 1 through 30. Submit the schedule through the backend adapter. Record the response status and error code, then repeat with zone IDs 1 through 20. No model or firmware override is included in the request.

## Triage request

Determine the expected behavior for this device using its registry record and the applicable approved requirements. Identify whether a software change is justified and describe the smallest verification that would establish the result. The ticket has no confirmed diagnosis or approved workaround.
```

### polMeta

`knowledge/confluence/controller-capacity-policy.md:1-10` (knowledge); SHA-256 `dee747968572194f8f5badee2a22e501e840ba51b6768084980693ed1ceffa0a`.

```text
# Controller capacity policy

Synthetic demonstration fixture. This is not a Data Honey customer record.

Document ID: controller-capacity-policy
Version: 1.0
Status: Approved
Owner: Scheduling Backend
Updated: 2026-09-15
Effective: 2026-09-15
```

### polRules

`knowledge/confluence/controller-capacity-policy.md:12-18` (knowledge); SHA-256 `dee747968572194f8f5badee2a22e501e840ba51b6768084980693ed1ceffa0a`.

```text
## Capacity rules

For a LEGACY controller with valid supported firmware metadata, the maximum is 20 zones.
For a PRO controller with firmware earlier than 3.2.0, the maximum is 20 zones.
For a PRO controller with firmware 3.2.0 or later, the maximum is 50 zones.
The boundary is inclusive: PRO firmware exactly 3.2.0 is eligible for 50 zones.
Firmware versions are exactly three nonnegative numeric components separated by dots. Compare components numerically: 3.10.0 is later than 3.2.0. Whitespace, signs, suffixes, missing components, and unrecognized model names are invalid metadata.
```

### polAuth

`knowledge/confluence/controller-capacity-policy.md:20-22` (knowledge); SHA-256 `dee747968572194f8f5badee2a22e501e840ba51b6768084980693ed1ceffa0a`.

```text
## Metadata authority

The backend resolves controller model and firmware from the device registry using the request's controller ID. Request-supplied model, firmware, or capability overrides must be rejected. Missing firmware, malformed firmware, or unrecognized model metadata must produce an explicit capability-metadata validation error; do not silently infer capacity or fall back to a different model.
```

### polSave

`knowledge/confluence/controller-capacity-policy.md:24-26` (knowledge); SHA-256 `dee747968572194f8f5badee2a22e501e840ba51b6768084980693ed1ceffa0a`.

```text
## Save behavior

Reject a request exceeding its device's capacity with HTTP 400 and `zone_limit_exceeded`. Validate before storing the schedule. A rejected request must neither allocate a saved schedule nor persist partial data. Successful saves return HTTP 201.
```

### polApply

`knowledge/confluence/controller-capacity-policy.md:28-30` (knowledge); SHA-256 `dee747968572194f8f5badee2a22e501e840ba51b6768084980693ed1ceffa0a`.

```text
## Applicability

Version 1.0 is approved and effective for the demo tickets dated after 2026-09-15. Historical ticket completion and customer expectations do not override these rules. This policy defines capacity; it does not authorize or prescribe a firmware upgrade.
```

### val

`app/schedule_validator.py:6-24` (code); SHA-256 `c733f6e5ddd96b19e3857ffff451fea9cba6e955969394623cfae7478750905f`.

```text
MAX_ZONES = 20


def validate_zones(zones, device):
    """Return a validation error string, or None when the schedule is valid."""
    if not isinstance(device, dict) or not isinstance(device.get("model"), str) or device["model"] not in {"LEGACY", "PRO"}:
        return "Controller model metadata is missing or unrecognized"
    firmware = device.get("firmware")
    if not isinstance(firmware, str) or re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", firmware) is None:
        return "Controller firmware metadata must contain three numeric components"
    if not isinstance(zones, list) or not zones:
        return "Zones must be a nonempty list"
    if any(not isinstance(zone, int) or isinstance(zone, bool) or zone <= 0 for zone in zones):
        return "Zone IDs must be positive integers"
    if len(set(zones)) != len(zones):
        return "Zone IDs must be unique"
    if len(zones) > MAX_ZONES:
        return f"Controller supports at most {MAX_ZONES} zones"
    return None
```

### svc

`app/schedule_service.py:16-35` (code); SHA-256 `3272360e047de58498ebbd2a143526362cd0325e386380eb9e4482141a0202de`.

```text
    def create_schedule(self, payload):
        if not isinstance(payload, dict):
            return self._invalid("Request must be an object")
        if set(payload) != {"controller_id", "zones"}:
            return self._invalid("Request must contain only controller_id and zones")
        controller_id = payload["controller_id"]
        if not isinstance(controller_id, str) or not controller_id.strip():
            return self._invalid("Controller ID must be a nonempty string")
        device = self.registry.get(controller_id)
        if device is None:
            return ApiResponse(404, {"error": "Controller was not found", "code": "controller_not_found"})
        error = validate_zones(payload["zones"], device)
        if error is not None:
            code = "zone_limit_exceeded" if error.startswith("Controller supports at most ") else "validation_error"
            return self._invalid(error, code)
        schedule_id = f"SCH-{self._next_id:04d}"
        schedule = {"id": schedule_id, "controller_id": controller_id, "zones": copy.deepcopy(payload["zones"])}
        self._schedules[schedule_id] = copy.deepcopy(schedule)
        self._next_id += 1
        return ApiResponse(201, copy.deepcopy(schedule))
```

### design

`knowledge/confluence/schedule-validation-design.md:16-18` (knowledge); SHA-256 `059ef4a98a77b0383f396e87442d201e6664129b02d91cba47a822f8e46b45dc`.

```text
## Authority and ownership

Scheduling Backend owns schedule-save validation and the backend service. The device registry supplies model and firmware facts. The approved controller capacity policy supplies the business requirements. Frontend validation helps the user construct a request; the backend independently enforces those requirements.
```

### hist981

`knowledge/jira/AG-981.md:12-14` (knowledge); SHA-256 `d737bc9999efb2ec5a6caccd6dccc99ec094c924f1cd160c3d9d2cfcabde0bed`.

```text
## Delivered scope

The schedule editor was updated to support selecting up to 50 zones for eligible Pro controllers. Eligibility and capacity are defined by the approved controller capacity policy. This ticket completed the frontend work only; completion does not establish that every backend path enforces the expanded policy.
```

### hist981Resp

`knowledge/jira/AG-981.md:16-18` (knowledge); SHA-256 `d737bc9999efb2ec5a6caccd6dccc99ec094c924f1cd160c3d9d2cfcabde0bed`.

```text
## Responsibility

Frontend Scheduling owns the editor experience. Scheduling Backend owns the schedule-save service and server-side validation. Model and firmware facts come from the device registry, rather than request-supplied capability claims.
```


## reproduce — AG-1423 — success

Run: reproduce-20261004T174423-cb702220 · Model: claude-sonnet-5-5 · Time: 8.66s

```diff
--- before/tests/test_reported_case.py
+++ after/tests/test_reported_case.py
@@ -0,0 +1,11 @@
+from app.api import create_schedule
+
+
+def test_reported_30_zones():
+    zones = list(range(1, 31))
+
+    response = create_schedule({"controller_id": "DEV-101", "zones": zones})
+
+    assert response.status_code == 201
+    assert response.body["controller_id"] == "DEV-101"
+    assert response.body["zones"] == zones

```

```json
{
  "exit_code": 1,
  "output": "F                                                                        [100%]\n=================================== FAILURES ===================================\n____________________________ test_reported_30_zones ____________________________\ntests/test_reported_case.py:9: in test_reported_30_zones\n    assert response.status_code == 201\nE   AssertionError: assert 400 == 201\nE    +  where 400 = ApiResponse(status_code=400, body={'error': 'Controller supports at most 20 zones', 'code': 'zone_limit_exceeded'}).status_code\n=========================== short test summary info ============================\nFAILED tests/test_reported_case.py::test_reported_30_zones - AssertionError: ...\n1 failed in 0.01s\n",
  "cases": [
    {
      "name": "test_reported_30_zones",
      "failed": true,
      "error": false,
      "skipped": false,
      "detail": "tests/test_reported_case.py:9: in test_reported_30_zones\n    assert response.status_code == 201\nE   AssertionError: assert 400 == 201\nE    +  where 400 = ApiResponse(status_code=400, body={'error': 'Controller supports at most 20 zones', 'code': 'zone_limit_exceeded'}).status_code"
    }
  ],
  "passed": 0,
  "failed": 1,
  "errors": 0,
  "skipped": 0,
  "observed_response": {
    "status_code": 400,
    "body": {
      "error": "Controller supports at most 20 zones",
      "code": "zone_limit_exceeded"
    }
  }
}
```

## fix — AG-1423 — success

Run: fix-20261004T174732-25241842 · Model: claude-sonnet-5-5 · Time: 13.91s

```diff
--- before/app/schedule_validator.py
+++ after/app/schedule_validator.py
@@ -4,6 +4,14 @@
 
 
 MAX_ZONES = 20
+PRO_MAX_ZONES = 50
+PRO_EXPANDED_FIRMWARE = (3, 2, 0)
+
+
+def _max_zones(device):
+    if device["model"] == "PRO" and tuple(int(part) for part in device["firmware"].split(".")) >= PRO_EXPANDED_FIRMWARE:
+        return PRO_MAX_ZONES
+    return MAX_ZONES
 
 
 def validate_zones(zones, device):
@@ -19,6 +27,7 @@
         return "Zone IDs must be positive integers"
     if len(set(zones)) != len(zones):
         return "Zone IDs must be unique"
-    if len(zones) > MAX_ZONES:
-        return f"Controller supports at most {MAX_ZONES} zones"
+    max_zones = _max_zones(device)
+    if len(zones) > max_zones:
+        return f"Controller supports at most {max_zones} zones"
     return None

```

```json
{
  "exit_code": 0,
  "output": ".......................                                                  [100%]\n23 passed in 0.01s\n",
  "cases": [
    {
      "name": "test_reported_30_zones",
      "failed": false,
      "error": false,
      "skipped": false,
      "detail": ""
    },
    {
      "name": "test_legacy_accepts_twenty",
      "failed": false,
      "error": false,
      "skipped": false,
      "detail": ""
    },
    {
      "name": "test_legacy_rejects_twenty_one",
      "failed": false,
      "error": false,
      "skipped": false,
      "detail": ""
    },
    {
      "name": "test_pro_accepts_ten",
      "failed": false,
      "error": false,
      "skipped": false,
      "detail": ""
    },
    {
      "name": "test_invalid_zones[zones0]",
      "failed": false,
      "error": false,
      "skipped": false,
      "detail": ""
    },
    {
      "name": "test_invalid_zones[None]",
      "failed": false,
      "error": false,
      "skipped": false,
      "detail": ""
    },
    {
      "name": "test_invalid_zones[1,2]",
      "failed": false,
      "error": false,
      "skipped": false,
      "detail": ""
    },
    {
      "name": "test_invalid_zones[zones3]",
      "failed": false,
      "error": false,
      "skipped": false,
      "detail": ""
    },
    {
      "name": "test_invalid_zones[zones4]",
      "failed": false,
      "error": false,
      "skipped": false,
      "detail": ""
    },
    {
      "name": "test_invalid_zones[zones5]",
      "failed": false,
      "error": false,
      "skipped": false,
      "detail": ""
    },
    {
      "name": "test_invalid_zones[zones6]",
      "failed": false,
      "error": false,
      "skipped": false,
      "detail": ""
    },
    {
      "name": "test_invalid_zones[zones7]",
      "failed": false,
      "error": false,
      "skipped": false,
      "detail": ""
    },
    {
      "name": "test_invalid_zones[zones8]",
      "failed": false,
      "error": false,
      "skipped": false,
      "detail": ""
    },
    {
      "name": "test_invalid_request[None]",
      "failed": false,
      "error": false,
      "skipped": false,
      "detail": ""
    },
    {
      "name": "test_invalid_request[payload1]",
      "failed": false,
      "error": false,
      "skipped": false,
      "detail": ""
    },
    {
      "name": "test_invalid_request[payload2]",
      "failed": false,
      "error": false,
      "skipped": false,
      "detail": ""
    },
    {
      "name": "test_invalid_request[payload3]",
      "failed": false,
      "error": false,
      "skipped": false,
      "detail": ""
    },
    {
      "name": "test_invalid_request[payload4]",
      "failed": false,
      "error": false,
      "skipped": false,
      "detail": ""
    },
    {
      "name": "test_invalid_request[payload5]",
      "failed": false,
      "error": false,
      "skipped": false,
      "detail": ""
    },
    {
      "name": "test_invalid_request[payload6]",
      "failed": false,
      "error": false,
      "skipped": false,
      "detail": ""
    },
    {
      "name": "test_unknown_controller",
      "failed": false,
      "error": false,
      "skipped": false,
      "detail": ""
    },
    {
      "name": "test_rejected_request_does_not_consume_an_id",
      "failed": false,
      "error": false,
      "skipped": false,
      "detail": ""
    },
    {
      "name": "test_saved_schedule_does_not_share_mutable_request_or_response",
      "failed": false,
      "error": false,
      "skipped": false,
      "detail": ""
    }
  ],
  "passed": 23,
  "failed": 0,
  "errors": 0,
  "skipped": 0
}
```

## verify —  — success

Run: verify-20261004T174929-a92358a0 · Model: no model · Time: 0.19s

```json
{
  "visible": {
    "exit_code": 0,
    "output": ".......................                                                  [100%]\n23 passed in 0.01s\n",
    "cases": [
      {
        "name": "test_reported_30_zones",
        "failed": false,
        "error": false,
        "skipped": false,
        "detail": ""
      },
      {
        "name": "test_legacy_accepts_twenty",
        "failed": false,
        "error": false,
        "skipped": false,
        "detail": ""
      },
      {
        "name": "test_legacy_rejects_twenty_one",
        "failed": false,
        "error": false,
        "skipped": false,
        "detail": ""
      },
      {
        "name": "test_pro_accepts_ten",
        "failed": false,
        "error": false,
        "skipped": false,
        "detail": ""
      },
      {
        "name": "test_invalid_zones[zones0]",
        "failed": false,
        "error": false,
        "skipped": false,
        "detail": ""
      },
      {
        "name": "test_invalid_zones[None]",
        "failed": false,
        "error": false,
        "skipped": false,
        "detail": ""
      },
      {
        "name": "test_invalid_zones[1,2]",
        "failed": false,
        "error": false,
        "skipped": false,
        "detail": ""
      },
      {
        "name": "test_invalid_zones[zones3]",
        "failed": false,
        "error": false,
        "skipped": false,
        "detail": ""
      },
      {
        "name": "test_invalid_zones[zones4]",
        "failed": false,
        "error": false,
        "skipped": false,
        "detail": ""
      },
      {
        "name": "test_invalid_zones[zones5]",
        "failed": false,
        "error": false,
        "skipped": false,
        "detail": ""
      },
      {
        "name": "test_invalid_zones[zones6]",
        "failed": false,
        "error": false,
        "skipped": false,
        "detail": ""
      },
      {
        "name": "test_invalid_zones[zones7]",
        "failed": false,
        "error": false,
        "skipped": false,
        "detail": ""
      },
      {
        "name": "test_invalid_zones[zones8]",
        "failed": false,
        "error": false,
        "skipped": false,
        "detail": ""
      },
      {
        "name": "test_invalid_request[None]",
        "failed": false,
        "error": false,
        "skipped": false,
        "detail": ""
      },
      {
        "name": "test_invalid_request[payload1]",
        "failed": false,
        "error": false,
        "skipped": false,
        "detail": ""
      },
      {
        "name": "test_invalid_request[payload2]",
        "failed": false,
        "error": false,
        "skipped": false,
        "detail": ""
      },
      {
        "name": "test_invalid_request[payload3]",
        "failed": false,
        "error": false,
        "skipped": false,
        "detail": ""
      },
      {
        "name": "test_invalid_request[payload4]",
        "failed": false,
        "error": false,
        "skipped": false,
        "detail": ""
      },
      {
        "name": "test_invalid_request[payload5]",
        "failed": false,
        "error": false,
        "skipped": false,
        "detail": ""
      },
      {
        "name": "test_invalid_request[payload6]",
        "failed": false,
        "error": false,
        "skipped": false,
        "detail": ""
      },
      {
        "name": "test_unknown_controller",
        "failed": false,
        "error": false,
        "skipped": false,
        "detail": ""
      },
      {
        "name": "test_rejected_request_does_not_consume_an_id",
        "failed": false,
        "error": false,
        "skipped": false,
        "detail": ""
      },
      {
        "name": "test_saved_schedule_does_not_share_mutable_request_or_response",
        "failed": false,
        "error": false,
        "skipped": false,
        "detail": ""
      }
    ],
    "passed": 23,
    "failed": 0,
    "errors": 0,
    "skipped": 0
  },
  "acceptance": {
    "status": "passed",
    "passed": 34,
    "failed": 0,
    "cases": [
      {
        "id": "registry_fixture",
        "status": "passed",
        "expected": {
          "DEV-101": {
            "model": "PRO",
            "firmware": "3.4.0"
          },
          "DEV-102": {
            "model": "PRO",
            "firmware": "3.1.0"
          },
          "DEV-103": {
            "model": "LEGACY",
            "firmware": "1.9.0"
          }
        },
        "observed": {
          "DEV-101": {
            "model": "PRO",
            "firmware": "3.4.0"
          },
          "DEV-102": {
            "model": "PRO",
            "firmware": "3.1.0"
          },
          "DEV-103": {
            "model": "LEGACY",
            "firmware": "1.9.0"
          }
        },
        "detail": "Requirement satisfied"
      },
      {
        "id": "pro_eligible_30",
        "status": "passed",
        "expected": 201,
        "observed": {
          "status_code": 201,
          "body": {
            "id": "SCH-0001",
            "controller_id": "DEV-101",
            "zones": [
              1,
              2,
              3,
              4,
              5,
              6,
              7,
              8,
              9,
              10,
              11,
              12,
              13,
              14,
              15,
              16,
              17,
              18,
              19,
              20,
              21,
              22,
              23,
              24,
              25,
              26,
              27,
              28,
              29,
              30
            ]
          }
        },
        "detail": "Requirement satisfied"
      },
      {
        "id": "pro_eligible_50",
        "status": "passed",
        "expected": 201,
        "observed": {
          "status_code": 201,
          "body": {
            "id": "SCH-0001",
            "controller_id": "DEV-101",
            "zones": [
              1,
              2,
              3,
              4,
              5,
              6,
              7,
              8,
              9,
              10,
              11,
              12,
              13,
              14,
              15,
              16,
              17,
              18,
              19,
              20,
              21,
              22,
              23,
              24,
              25,
              26,
              27,
              28,
              29,
              30,
              31,
              32,
              33,
              34,
              35,
              36,
              37,
              38,
              39,
              40,
              41,
              42,
              43,
              44,
              45,
              46,
              47,
              48,
              49,
              50
            ]
          }
        },
        "detail": "Requirement satisfied"
      },
      {
        "id": "pro_eligible_51",
        "status": "passed",
        "expected": 400,
        "observed": {
          "status_code": 400,
          "body": {
            "error": "Controller supports at most 50 zones",
            "code": "zone_limit_exceeded"
          }
        },
        "detail": "Requirement satisfied"
      },
      {
        "id": "pro_old_20",
        "status": "passed",
        "expected": 201,
        "observed": {
          "status_code": 201,
          "body": {
            "id": "SCH-0001",
            "controller_id": "DEV-102",
            "zones": [
              1,
              2,
              3,
              4,
              5,
              6,
              7,
              8,
              9,
              10,
              11,
              12,
              13,
              14,
              15,
              16,
              17,
              18,
              19,
              20
            ]
          }
        },
        "detail": "Requirement satisfied"
      },
      {
        "id": "pro_old_21",
        "status": "passed",
        "expected": 400,
        "observed": {
          "status_code": 400,
          "body": {
            "error": "Controller supports at most 20 zones",
            "code": "zone_limit_exceeded"
          }
        },
        "detail": "Requirement satisfied"
      },
      {
        "id": "legacy_20",
        "status": "passed",
        "expected": 201,
        "observed": {
          "status_code": 201,
          "body": {
            "id": "SCH-0001",
            "controller_id": "DEV-103",
            "zones": [
              1,
              2,
              3,
              4,
              5,
              6,
              7,
              8,
              9,
              10,
              11,
              12,
              13,
              14,
              15,
              16,
              17,
              18,
              19,
              20
            ]
          }
        },
        "detail": "Requirement satisfied"
      },
      {
        "id": "legacy_21",
        "status": "passed",
        "expected": 400,
        "observed": {
          "status_code": 400,
          "body": {
            "error": "Controller supports at most 20 zones",
            "code": "zone_limit_exceeded"
          }
        },
        "detail": "Requirement satisfied"
      },
      {
        "id": "unknown_controller",
        "status": "passed",
        "expected": 404,
        "observed": {
          "status_code": 404,
          "body": {
            "error": "Controller was not found",
            "code": "controller_not_found"
          }
        },
        "detail": "Requirement satisfied"
      },
      {
        "id": "pro_boundary_3_2_0",
        "status": "passed",
        "expected": 201,
        "observed": {
          "status_code": 201,
          "body": {
            "id": "SCH-0001",
            "controller_id": "EDGE",
            "zones": [
              1,
              2,
              3,
              4,
              5,
              6,
              7,
              8,
              9,
              10,
              11,
              12,
              13,
              14,
              15,
              16,
              17,
              18,
              19,
              20,
              21,
              22,
              23,
              24,
              25,
              26,
              27,
              28,
              29,
              30,
              31,
              32,
              33,
              34,
              35,
              36,
              37,
              38,
              39,
              40,
              41,
              42,
              43,
              44,
              45,
              46,
              47,
              48,
              49,
              50
            ]
          }
        },
        "detail": "Requirement satisfied"
      },
      {
        "id": "pro_below_boundary_3_1_99",
        "status": "passed",
        "expected": 400,
        "observed": {
          "status_code": 400,
          "body": {
            "error": "Controller supports at most 20 zones",
            "code": "zone_limit_exceeded"
          }
        },
        "detail": "Requirement satisfied"
      },
      {
        "id": "pro_numeric_3_10_0",
        "status": "passed",
        "expected": 201,
        "observed": {
          "status_code": 201,
          "body": {
            "id": "SCH-0001",
            "controller_id": "EDGE",
            "zones": [
              1,
              2,
              3,
              4,
              5,
              6,
              7,
              8,
              9,
              10,
              11,
              12,
              13,
              14,
              15,
              16,
              17,
              18,
              19,
              20,
              21,
              22,
              23,
              24,
              25,
              26,
              27,
              28,
              29,
              30,
              31,
              32,
              33,
              34,
              35,
              36,
              37,
              38,
              39,
              40,
              41,
              42,
              43,
              44,
              45,
              46,
              47,
              48,
              49,
              50
            ]
          }
        },
        "detail": "Requirement satisfied"
      },
      {
        "id": "missing_firmware",
        "status": "passed",
        "expected": 400,
        "observed": {
          "status_code": 400,
          "body": {
            "error": "Controller firmware metadata must contain three numeric components",
            "code": "validation_error"
          }
        },
        "detail": "Requirement satisfied"
      },
      {
        "id": "malformed_firmware_1",
        "status": "passed",
        "expected": 400,
        "observed": {
          "status_code": 400,
          "body": {
            "error": "Controller firmware metadata must contain three numeric components",
            "code": "validation_error"
          }
        },
        "detail": "Requirement satisfied"
      },
      {
        "id": "malformed_firmware_2",
        "status": "passed",
        "expected": 400,
        "observed": {
          "status_code": 400,
          "body": {
            "error": "Controller firmware metadata must contain three numeric components",
            "code": "validation_error"
          }
        },
        "detail": "Requirement satisfied"
      },
      {
        "id": "malformed_firmware_3",
        "status": "passed",
        "expected": 400,
        "observed": {
          "status_code": 400,
          "body": {
            "error": "Controller firmware metadata must contain three numeric components",
            "code": "validation_error"
          }
        },
        "detail": "Requirement satisfied"
      },
      {
        "id": "malformed_firmware_4",
        "status": "passed",
        "expected": 400,
        "observed": {
          "status_code": 400,
          "body": {
            "error": "Controller firmware metadata must contain three numeric components",
            "code": "validation_error"
          }
        },
        "detail": "Requirement satisfied"
      },
      {
        "id": "malformed_firmware_5",
        "status": "passed",
        "expected": 400,
        "observed": {
          "status_code": 400,
          "body": {
            "error": "Controller firmware metadata must contain three numeric components",
            "code": "validation_error"
          }
        },
        "detail": "Requirement satisfied"
      },
      {
        "id": "malformed_firmware_6",
        "status": "passed",
        "expected": 400,
        "observed": {
          "status_code": 400,
          "body": {
            "error": "Controller firmware metadata must contain three numeric components",
            "code": "validation_error"
          }
        },
        "detail": "Requirement satisfied"
      },
      {
        "id": "malformed_firmware_7",
        "status": "passed",
        "expected": 400,
        "observed": {
          "status_code": 400,
          "body": {
            "error": "Controller firmware metadata must contain three numeric components",
            "code": "validation_error"
          }
        },
        "detail": "Requirement satisfied"
      },
      {
        "id": "malformed_firmware_8",
        "status": "passed",
        "expected": 400,
        "observed": {
          "status_code": 400,
          "body": {
            "error": "Controller firmware metadata must contain three numeric components",
            "code": "validation_error"
          }
        },
        "detail": "Requirement satisfied"
      },
      {
        "id": "missing_model",
        "status": "passed",
        "expected": 400,
        "observed": {
          "status_code": 400,
          "body": {
            "error": "Controller model metadata is missing or unrecognized",
            "code": "validation_error"
          }
        },
        "detail": "Requirement satisfied"
      },
      {
        "id": "unknown_model",
        "status": "passed",
        "expected": 400,
        "observed": {
          "status_code": 400,
          "body": {
            "error": "Controller model metadata is missing or unrecognized",
            "code": "validation_error"
          }
        },
        "detail": "Requirement satisfied"
      },
      {
        "id": "invalid_model_type",
        "status": "passed",
        "expected": 400,
        "observed": {
          "status_code": 400,
          "body": {
            "error": "Controller model metadata is missing or unrecognized",
            "code": "validation_error"
          }
        },
        "detail": "Requirement satisfied"
      },
      {
        "id": "invalid_device_record",
        "status": "passed",
        "expected": 400,
        "observed": {
          "status_code": 400,
          "body": {
            "error": "Controller model metadata is missing or unrecognized",
            "code": "validation_error"
          }
        },
        "detail": "Requirement satisfied"
      },
      {
        "id": "spoofed_model",
        "status": "passed",
        "expected": 400,
        "observed": {
          "status_code": 400,
          "body": {
            "error": "Request must contain only controller_id and zones",
            "code": "validation_error"
          }
        },
        "detail": "Requirement satisfied"
      },
      {
        "id": "spoofed_firmware",
        "status": "passed",
        "expected": 400,
        "observed": {
          "status_code": 400,
          "body": {
            "error": "Request must contain only controller_id and zones",
            "code": "validation_error"
          }
        },
        "detail": "Requirement satisfied"
      },
      {
        "id": "duplicate_zones",
        "status": "passed",
        "expected": 400,
        "observed": {
          "status_code": 400,
          "body": {
            "error": "Zone IDs must be unique",
            "code": "validation_error"
          }
        },
        "detail": "Requirement satisfied"
      },
      {
        "id": "boolean_zone",
        "status": "passed",
        "expected": 400,
        "observed": {
          "status_code": 400,
          "body": {
            "error": "Zone IDs must be positive integers",
            "code": "validation_error"
          }
        },
        "detail": "Requirement satisfied"
      },
      {
        "id": "zero_zone",
        "status": "passed",
        "expected": 400,
        "observed": {
          "status_code": 400,
          "body": {
            "error": "Zone IDs must be positive integers",
            "code": "validation_error"
          }
        },
        "detail": "Requirement satisfied"
      },
      {
        "id": "negative_zone",
        "status": "passed",
        "expected": 400,
        "observed": {
          "status_code": 400,
          "body": {
            "error": "Zone IDs must be positive integers",
            "code": "validation_error"
          }
        },
        "detail": "Requirement satisfied"
      },
      {
        "id": "string_zone",
        "status": "passed",
        "expected": 400,
        "observed": {
          "status_code": 400,
          "body": {
            "error": "Zone IDs must be positive integers",
            "code": "validation_error"
          }
        },
        "detail": "Requirement satisfied"
      },
      {
        "id": "empty_zones",
        "status": "passed",
        "expected": 400,
        "observed": {
          "status_code": 400,
          "body": {
            "error": "Zones must be a nonempty list",
            "code": "validation_error"
          }
        },
        "detail": "Requirement satisfied"
      },
      {
        "id": "rejection_preserves_id",
        "status": "passed",
        "expected": "First accepted schedule is SCH-0001",
        "observed": {
          "status_code": 201,
          "body": {
            "id": "SCH-0001",
            "controller_id": "DEV-103",
            "zones": [
              1
            ]
          }
        },
        "detail": "Requirement satisfied"
      }
    ]
  }
}
```

## investigate — AG-1424 — partial

Run: investigate-20261004T175004-06c31371 · Model: claude-sonnet-5-5 · Time: 29.19s

Problem: policy: unknown status requires an explicit unknown statement
## investigate — AG-1424 — success

Run: investigate-20261004T181657-5171cad2 · Model: claude-sonnet-5-5 · Time: 36.5s

# Decision packet: AG-1424

Source provenance and read coverage are mechanically checked. Claim support requires human review. See run metadata for the actual model and run status.

**Device:** DEV-102; model PRO; firmware 3.1.0. [reg_model](#reg_model) [reg_fw](#reg_fw)

**Policy (established):** The controller capacity policy is Approved and effective 2026-09-15, applying to demo tickets dated after that. It caps PRO firmware earlier than 3.2.0 at 20 zones (3.2.0 or later: 50), and over-capacity saves must return HTTP 400 `zone_limit_exceeded`. [pol_meta](#pol_meta) [pol_rules](#pol_rules) [pol_save](#pol_save) [pol_apply](#pol_apply)

**Diagnosis (expected_rejection):** DEV-102 is PRO on firmware 3.1.0, below 3.2.0, so a 30-zone save should be rejected, and the backend code matches this. The customer's belief that every Pro controller accepts larger schedules is not an approved requirement. [reg_model](#reg_model) [reg_fw](#reg_fw) [pol_rules](#pol_rules) [code_validator](#code_validator) [code_service](#code_service) [ticket_report](#ticket_report)

## Starting files

- `app/schedule_validator.py:11-33` — Contains the PRO/firmware threshold logic and the over-capacity error that produces the rejection. [code_validator](#code_validator)

- `app/schedule_service.py:24-35` — Resolves the device from the registry, validates before storing, and maps the limit error to HTTP 400 `zone_limit_exceeded`. [code_service](#code_service)

**Execution path:** `create_schedule` looks up DEV-102 in the registry (PRO, 3.1.0) and calls `validate_zones`, where `_max_zones` returns 20 because (3,1,0) is below (3,2,0). The 30-zone request fails the length check and the service returns 400 `zone_limit_exceeded` before anything is stored. [code_service](#code_service) [code_validator](#code_validator) [reg_model](#reg_model) [reg_fw](#reg_fw)

## History and ownership

- AG-981 delivered only the editor's 50-zone selection for eligible Pro controllers and does not establish that backend paths enforce the expanded policy. [hist_981_scope](#hist_981_scope)

**Owner:** The Scheduling Backend owns the schedule-save service, server-side validation and the capacity policy. The ticket itself is owned by Support Triage. [hist_981_resp](#hist_981_resp) [pol_meta](#pol_meta) [ticket_meta](#ticket_meta)

**Next action:** Tell support the 20-zone limit for DEV-102 (PRO, 3.1.0) is expected under the approved policy, and ask them to confirm the observed 30-zone failure and 20-zone success. Do not change backend code or promise a firmware upgrade, since no approved procedure exists. [pol_rules](#pol_rules) [pol_apply](#pol_apply) [ticket_triage](#ticket_triage)

## Open questions

- No actual response from running the reproduction is attached; the reported 400 and 20-zone success come from the ticket.

- No approved firmware-upgrade procedure exists, and the registry does not say whether DEV-102 can be upgraded.

- AG-981's status, dates and owner metadata were not read, and I did not inspect the tests or the registry loader.

## Captured citations

### reg_model

`app/devices.json:7-7` (registry); SHA-256 `cc8b7f966610ce03ee8ba89d4733948fb98035a7ed4a8c897988d90799943c5c`.

```text
    "model": "PRO",
```

### reg_fw

`app/devices.json:8-8` (registry); SHA-256 `cc8b7f966610ce03ee8ba89d4733948fb98035a7ed4a8c897988d90799943c5c`.

```text
    "firmware": "3.1.0"
```

### pol_meta

`knowledge/confluence/controller-capacity-policy.md:5-10` (knowledge); SHA-256 `dee747968572194f8f5badee2a22e501e840ba51b6768084980693ed1ceffa0a`.

```text
Document ID: controller-capacity-policy
Version: 1.0
Status: Approved
Owner: Scheduling Backend
Updated: 2026-09-15
Effective: 2026-09-15
```

### pol_rules

`knowledge/confluence/controller-capacity-policy.md:14-18` (knowledge); SHA-256 `dee747968572194f8f5badee2a22e501e840ba51b6768084980693ed1ceffa0a`.

```text
For a LEGACY controller with valid supported firmware metadata, the maximum is 20 zones.
For a PRO controller with firmware earlier than 3.2.0, the maximum is 20 zones.
For a PRO controller with firmware 3.2.0 or later, the maximum is 50 zones.
The boundary is inclusive: PRO firmware exactly 3.2.0 is eligible for 50 zones.
Firmware versions are exactly three nonnegative numeric components separated by dots. Compare components numerically: 3.10.0 is later than 3.2.0. Whitespace, signs, suffixes, missing components, and unrecognized model names are invalid metadata.
```

### pol_save

`knowledge/confluence/controller-capacity-policy.md:26-26` (knowledge); SHA-256 `dee747968572194f8f5badee2a22e501e840ba51b6768084980693ed1ceffa0a`.

```text
Reject a request exceeding its device's capacity with HTTP 400 and `zone_limit_exceeded`. Validate before storing the schedule. A rejected request must neither allocate a saved schedule nor persist partial data. Successful saves return HTTP 201.
```

### pol_apply

`knowledge/confluence/controller-capacity-policy.md:28-30` (knowledge); SHA-256 `dee747968572194f8f5badee2a22e501e840ba51b6768084980693ed1ceffa0a`.

```text
## Applicability

Version 1.0 is approved and effective for the demo tickets dated after 2026-09-15. Historical ticket completion and customer expectations do not override these rules. This policy defines capacity; it does not authorize or prescribe a firmware upgrade.
```

### code_validator

`app/schedule_validator.py:11-33` (code); SHA-256 `3b4e61a7df033bf3e8a1705693dc543ceab02d95dad536880d78ca006f7dcaec`.

```text
def _max_zones(device):
    if device["model"] == "PRO" and tuple(int(part) for part in device["firmware"].split(".")) >= PRO_EXPANDED_FIRMWARE:
        return PRO_MAX_ZONES
    return MAX_ZONES


def validate_zones(zones, device):
    """Return a validation error string, or None when the schedule is valid."""
    if not isinstance(device, dict) or not isinstance(device.get("model"), str) or device["model"] not in {"LEGACY", "PRO"}:
        return "Controller model metadata is missing or unrecognized"
    firmware = device.get("firmware")
    if not isinstance(firmware, str) or re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", firmware) is None:
        return "Controller firmware metadata must contain three numeric components"
    if not isinstance(zones, list) or not zones:
        return "Zones must be a nonempty list"
    if any(not isinstance(zone, int) or isinstance(zone, bool) or zone <= 0 for zone in zones):
        return "Zone IDs must be positive integers"
    if len(set(zones)) != len(zones):
        return "Zone IDs must be unique"
    max_zones = _max_zones(device)
    if len(zones) > max_zones:
        return f"Controller supports at most {max_zones} zones"
    return None
```

### code_service

`app/schedule_service.py:24-35` (code); SHA-256 `3272360e047de58498ebbd2a143526362cd0325e386380eb9e4482141a0202de`.

```text
        device = self.registry.get(controller_id)
        if device is None:
            return ApiResponse(404, {"error": "Controller was not found", "code": "controller_not_found"})
        error = validate_zones(payload["zones"], device)
        if error is not None:
            code = "zone_limit_exceeded" if error.startswith("Controller supports at most ") else "validation_error"
            return self._invalid(error, code)
        schedule_id = f"SCH-{self._next_id:04d}"
        schedule = {"id": schedule_id, "controller_id": controller_id, "zones": copy.deepcopy(payload["zones"])}
        self._schedules[schedule_id] = copy.deepcopy(schedule)
        self._next_id += 1
        return ApiResponse(201, copy.deepcopy(schedule))
```

### ticket_report

`knowledge/jira/AG-1424.md:13-13` (knowledge); SHA-256 `be5a02713e46cd368ae8f8aa03433a8cef78850eba04f213d90fa01aa6d26f42`.

```text
The customer reports that saving 30 zones on controller DEV-102 returns HTTP 400 with `zone_limit_exceeded`. Saving 20 zones on the same controller succeeds. The customer believes that every Pro controller should accept larger schedules.
```

### ticket_triage

`knowledge/jira/AG-1424.md:19-21` (knowledge); SHA-256 `be5a02713e46cd368ae8f8aa03433a8cef78850eba04f213d90fa01aa6d26f42`.

```text
## Triage request

Determine the expected behavior for this device using its registry record and the applicable approved requirements. Do not treat the customer's assumption as an approved requirement. There is no confirmed diagnosis or approved firmware-upgrade procedure attached to this ticket.
```

### ticket_meta

`knowledge/jira/AG-1424.md:5-9` (knowledge); SHA-256 `be5a02713e46cd368ae8f8aa03433a8cef78850eba04f213d90fa01aa6d26f42`.

```text
Document ID: AG-1424
Version: 1.0
Status: Open
Owner: Support Triage
Updated: 2026-10-03
```

### hist_981_scope

`knowledge/jira/AG-981.md:12-14` (knowledge); SHA-256 `d737bc9999efb2ec5a6caccd6dccc99ec094c924f1cd160c3d9d2cfcabde0bed`.

```text
## Delivered scope

The schedule editor was updated to support selecting up to 50 zones for eligible Pro controllers. Eligibility and capacity are defined by the approved controller capacity policy. This ticket completed the frontend work only; completion does not establish that every backend path enforces the expanded policy.
```

### hist_981_resp

`knowledge/jira/AG-981.md:16-18` (knowledge); SHA-256 `d737bc9999efb2ec5a6caccd6dccc99ec094c924f1cd160c3d9d2cfcabde0bed`.

```text
## Responsibility

Frontend Scheduling owns the editor experience. Scheduling Backend owns the schedule-save service and server-side validation. Model and firmware facts come from the device registry, rather than request-supplied capability claims.
```

