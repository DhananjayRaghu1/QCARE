# Recorded workflow: rehearsal-2

Synthetic fixtures. Model traces and test results are actual executions.
Source checks establish provenance; human review of claim support remains pending.

## investigate — AG-1423 — success

Run: investigate-20261004T174952-5155ed68 · Model: claude-sonnet-5-5 · Time: 18.84s

# Decision packet: AG-1423

Source provenance and read coverage are mechanically checked. Claim support requires human review. See run metadata for the actual model and run status.

**Device:** DEV-101; model PRO; firmware 3.4.0. [reg](#reg)

**Policy (established):** The approved, effective policy gives a PRO controller on firmware 3.2.0 or later a 50-zone maximum, resolved from the registry, and requires `zone_limit_exceeded` only above device capacity. It applies to tickets dated after 2026-09-15, and AG-1423 is dated 2026-10-02. [polmeta](#polmeta) [polrules](#polrules) [polauth](#polauth) [polapply](#polapply)

**Diagnosis (investigate_mismatch):** DEV-101 (PRO 3.4.0) should accept 30 zones, but the validator applies a flat 20-zone cap, so the 400 contradicts the policy. This is read from code only, since nothing was executed. [reg](#reg) [polrules](#polrules) [code_val](#code_val) [code_svc](#code_svc) [ticket_rep](#ticket_rep)

## Starting files

- `app/schedule_validator.py:6-24` — The hard-coded MAX_ZONES = 20 is compared against len(zones) without using the device's model or firmware. [code_val](#code_val)

- `app/schedule_service.py:24-30` — The service looks up the device in the registry and maps the validator's message to `zone_limit_exceeded`. [code_svc](#code_svc)

**Execution path:** `create_schedule` fetches the DEV-101 record and calls `validate_zones`. That function passes the metadata checks, then rejects 30 zones because `len(zones) &gt; 20`, and the service returns 400 `zone_limit_exceeded`. [code_svc](#code_svc) [code_val](#code_val)

## History and ownership

- AG-981 (Closed, Frontend Scheduling, 2026-09-18) delivered only the editor's 50-zone selection for eligible Pro controllers. This is consistent with the editor allowing 30 selections, but it is not a backend verification. [h981meta](#h981meta) [h981scope](#h981scope)

**Owner:** Scheduling Backend owns the schedule-save service and server-side validation, so the fix belongs with them. AG-1423 is currently held by Support Triage. [valdesign](#valdesign) [polmeta](#polmeta) [ticket_meta](#ticket_meta)

**Next action:** Change the validator to derive capacity from the registry model and firmware per the policy, including the inclusive 3.2.0 boundary and numeric comparison. Verify with the smallest test: DEV-101 with zones 1–30 returns 201, and 1–51 returns 400 `zone_limit_exceeded`. [polrules](#polrules) [polsave](#polsave)

## Open questions

- The ticket's actual response was not reproduced, so the observed 400 comes from the customer report plus code reading.

- Whether other code paths, such as the device registry loader or the browser editor, affect this save is unknown, because only the two backend files were read.

- No approved workaround or firmware upgrade procedure exists.

## Captured citations

### reg

`app/devices.json:2-5` (registry); SHA-256 `cc8b7f966610ce03ee8ba89d4733948fb98035a7ed4a8c897988d90799943c5c`.

```text
  "DEV-101": {
    "model": "PRO",
    "firmware": "3.4.0"
  },
```

### polmeta

`knowledge/confluence/controller-capacity-policy.md:5-10` (knowledge); SHA-256 `dee747968572194f8f5badee2a22e501e840ba51b6768084980693ed1ceffa0a`.

```text
Document ID: controller-capacity-policy
Version: 1.0
Status: Approved
Owner: Scheduling Backend
Updated: 2026-09-15
Effective: 2026-09-15
```

### polrules

`knowledge/confluence/controller-capacity-policy.md:14-18` (knowledge); SHA-256 `dee747968572194f8f5badee2a22e501e840ba51b6768084980693ed1ceffa0a`.

```text
For a LEGACY controller with valid supported firmware metadata, the maximum is 20 zones.
For a PRO controller with firmware earlier than 3.2.0, the maximum is 20 zones.
For a PRO controller with firmware 3.2.0 or later, the maximum is 50 zones.
The boundary is inclusive: PRO firmware exactly 3.2.0 is eligible for 50 zones.
Firmware versions are exactly three nonnegative numeric components separated by dots. Compare components numerically: 3.10.0 is later than 3.2.0. Whitespace, signs, suffixes, missing components, and unrecognized model names are invalid metadata.
```

### polauth

`knowledge/confluence/controller-capacity-policy.md:20-22` (knowledge); SHA-256 `dee747968572194f8f5badee2a22e501e840ba51b6768084980693ed1ceffa0a`.

```text
## Metadata authority

The backend resolves controller model and firmware from the device registry using the request's controller ID. Request-supplied model, firmware, or capability overrides must be rejected. Missing firmware, malformed firmware, or unrecognized model metadata must produce an explicit capability-metadata validation error; do not silently infer capacity or fall back to a different model.
```

### polsave

`knowledge/confluence/controller-capacity-policy.md:24-26` (knowledge); SHA-256 `dee747968572194f8f5badee2a22e501e840ba51b6768084980693ed1ceffa0a`.

```text
## Save behavior

Reject a request exceeding its device's capacity with HTTP 400 and `zone_limit_exceeded`. Validate before storing the schedule. A rejected request must neither allocate a saved schedule nor persist partial data. Successful saves return HTTP 201.
```

### polapply

`knowledge/confluence/controller-capacity-policy.md:28-30` (knowledge); SHA-256 `dee747968572194f8f5badee2a22e501e840ba51b6768084980693ed1ceffa0a`.

```text
## Applicability

Version 1.0 is approved and effective for the demo tickets dated after 2026-09-15. Historical ticket completion and customer expectations do not override these rules. This policy defines capacity; it does not authorize or prescribe a firmware upgrade.
```

### code_val

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

### code_svc

`app/schedule_service.py:24-30` (code); SHA-256 `3272360e047de58498ebbd2a143526362cd0325e386380eb9e4482141a0202de`.

```text
        device = self.registry.get(controller_id)
        if device is None:
            return ApiResponse(404, {"error": "Controller was not found", "code": "controller_not_found"})
        error = validate_zones(payload["zones"], device)
        if error is not None:
            code = "zone_limit_exceeded" if error.startswith("Controller supports at most ") else "validation_error"
            return self._invalid(error, code)
```

### ticket_rep

`knowledge/jira/AG-1423.md:11-17` (knowledge); SHA-256 `97ae812e973335c64c587a93d06bece10ee1d24371010164e20ff456a03dbfda`.

```text
## Reported behavior

The customer reports that saving 30 zones on controller DEV-101 returns HTTP 400 with `zone_limit_exceeded`. Saving 20 zones on the same controller succeeds. The browser editor allows the customer to select the 30 zones before saving.

## Reproduction

Use `controller_id: DEV-101` and zone IDs 1 through 30. Submit the schedule through the backend adapter. Record the response status and error code, then repeat with zone IDs 1 through 20. No model or firmware override is included in the request.
```

### ticket_meta

`knowledge/jira/AG-1423.md:5-9` (knowledge); SHA-256 `97ae812e973335c64c587a93d06bece10ee1d24371010164e20ff456a03dbfda`.

```text
Document ID: AG-1423
Version: 1.0
Status: Open
Owner: Support Triage
Updated: 2026-10-02
```

### h981meta

`knowledge/jira/AG-981.md:5-10` (knowledge); SHA-256 `d737bc9999efb2ec5a6caccd6dccc99ec094c924f1cd160c3d9d2cfcabde0bed`.

```text
Document ID: AG-981
Version: 1.0
Status: Closed
Owner: Frontend Scheduling
Updated: 2026-09-18
Completed: 2026-09-18
```

### h981scope

`knowledge/jira/AG-981.md:12-14` (knowledge); SHA-256 `d737bc9999efb2ec5a6caccd6dccc99ec094c924f1cd160c3d9d2cfcabde0bed`.

```text
## Delivered scope

The schedule editor was updated to support selecting up to 50 zones for eligible Pro controllers. Eligibility and capacity are defined by the approved controller capacity policy. This ticket completed the frontend work only; completion does not establish that every backend path enforces the expanded policy.
```

### valdesign

`knowledge/confluence/schedule-validation-design.md:16-18` (knowledge); SHA-256 `059ef4a98a77b0383f396e87442d201e6664129b02d91cba47a822f8e46b45dc`.

```text
## Authority and ownership

Scheduling Backend owns schedule-save validation and the backend service. The device registry supplies model and firmware facts. The approved controller capacity policy supplies the business requirements. Frontend validation helps the user construct a request; the backend independently enforces those requirements.
```


## reproduce — AG-1423 — success

Run: reproduce-20261004T181627-973edfbb · Model: claude-sonnet-5-5 · Time: 10.22s

```diff
--- before/tests/test_reported_case.py
+++ after/tests/test_reported_case.py
@@ -0,0 +1,7 @@
+from app.api import create_schedule
+
+
+def test_reported_30_zones():
+    response = create_schedule({"controller_id": "DEV-101", "zones": list(range(1, 31))})
+
+    assert response.status_code == 201

```

```json
{
  "exit_code": 1,
  "output": "F                                                                        [100%]\n=================================== FAILURES ===================================\n____________________________ test_reported_30_zones ____________________________\ntests/test_reported_case.py:7: in test_reported_30_zones\n    assert response.status_code == 201\nE   AssertionError: assert 400 == 201\nE    +  where 400 = ApiResponse(status_code=400, body={'error': 'Controller supports at most 20 zones', 'code': 'zone_limit_exceeded'}).status_code\n=========================== short test summary info ============================\nFAILED tests/test_reported_case.py::test_reported_30_zones - AssertionError: ...\n1 failed in 0.01s\n",
  "cases": [
    {
      "name": "test_reported_30_zones",
      "failed": true,
      "error": false,
      "skipped": false,
      "detail": "tests/test_reported_case.py:7: in test_reported_30_zones\n    assert response.status_code == 201\nE   AssertionError: assert 400 == 201\nE    +  where 400 = ApiResponse(status_code=400, body={'error': 'Controller supports at most 20 zones', 'code': 'zone_limit_exceeded'}).status_code"
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

Run: fix-20261004T182021-6b57d3e8 · Model: claude-sonnet-5-5 · Time: 9.2s

```diff
--- before/app/schedule_validator.py
+++ after/app/schedule_validator.py
@@ -4,6 +4,8 @@
 
 
 MAX_ZONES = 20
+PRO_EXPANDED_MAX_ZONES = 50
+PRO_EXPANDED_FIRMWARE = (3, 2, 0)
 
 
 def validate_zones(zones, device):
@@ -19,6 +21,9 @@
         return "Zone IDs must be positive integers"
     if len(set(zones)) != len(zones):
         return "Zone IDs must be unique"
-    if len(zones) > MAX_ZONES:
-        return f"Controller supports at most {MAX_ZONES} zones"
+    max_zones = MAX_ZONES
+    if device["model"] == "PRO" and tuple(int(part) for part in firmware.split(".")) >= PRO_EXPANDED_FIRMWARE:
+        max_zones = PRO_EXPANDED_MAX_ZONES
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

Run: verify-20261004T182236-c9849f78 · Model: no model · Time: 0.19s

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

## investigate — AG-1424 — success

Run: investigate-20261004T182309-1ea4b1c4 · Model: claude-sonnet-5-5 · Time: 30.13s

# Decision packet: AG-1424

Source provenance and read coverage are mechanically checked. Claim support requires human review. See run metadata for the actual model and run status.

**Device:** DEV-102; model PRO; firmware 3.1.0. [reg](#reg)

**Policy (established):** The approved, effective (2026-09-15) Scheduling Backend capacity policy caps PRO firmware earlier than 3.2.0 at 20 zones and requires HTTP 400 `zone_limit_exceeded` above capacity. The customer's belief that all Pro controllers accept larger schedules is not a requirement. [pol_meta](#pol_meta) [pol_rules](#pol_rules) [pol_save](#pol_save) [pol_apply](#pol_apply)

**Diagnosis (expected_rejection):** DEV-102 is PRO on 3.1.0, so 30 zones exceeds its 20-zone limit and the 400 `zone_limit_exceeded` matches policy; 20 zones succeeding is also consistent. The backend code matches the policy and no mismatch was found. [reg](#reg) [pol_rules](#pol_rules) [val_logic](#val_logic) [svc_flow](#svc_flow) [ticket_rep](#ticket_rep)

## Starting files

- `app/schedule_validator.py:24-28` — Applies the 20/50 zone limit using the PRO and 3.2.0 firmware comparison. [val_logic](#val_logic)

- `app/schedule_service.py:24-30` — Resolves the device from the registry and maps the capacity error to HTTP 400 `zone_limit_exceeded`. [svc_flow](#svc_flow)

**Execution path:** `create_schedule` looks up DEV-102 in the registry, then `validate_zones` computes a 20-zone maximum for PRO 3.1.0. The 30-zone request fails the length check and returns 400 `zone_limit_exceeded` before any schedule is stored. [svc_flow](#svc_flow) [val_logic](#val_logic)

## History and ownership

- AG-981 delivered only the frontend editor support for up to 50 zones on eligible Pro controllers and does not establish backend enforcement; its dates and status were not captured. [ag981_scope](#ag981_scope)

**Owner:** Scheduling Backend owns the capacity policy and schedule-save validation; Support Triage owns the ticket. [pol_meta](#pol_meta) [design_owner](#design_owner) [ticket_meta](#ticket_meta)

**Next action:** Reply that DEV-102's registry record (PRO, 3.1.0) limits it to 20 zones under the approved policy. Make no backend code change; no approved firmware-upgrade procedure exists in the evidence. [reg](#reg) [pol_rules](#pol_rules) [pol_apply](#pol_apply) [ticket_triage](#ticket_triage)

## Open questions

- Whether registry firmware 3.1.0 matches the physical device is unverified.

- No approved firmware-upgrade procedure is available.

- The HTTP responses were not reproduced because commands cannot be run.

## Captured citations

### reg

`app/devices.json:6-9` (registry); SHA-256 `cc8b7f966610ce03ee8ba89d4733948fb98035a7ed4a8c897988d90799943c5c`.

```text
  "DEV-102": {
    "model": "PRO",
    "firmware": "3.1.0"
  },
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

`knowledge/confluence/controller-capacity-policy.md:24-26` (knowledge); SHA-256 `dee747968572194f8f5badee2a22e501e840ba51b6768084980693ed1ceffa0a`.

```text
## Save behavior

Reject a request exceeding its device's capacity with HTTP 400 and `zone_limit_exceeded`. Validate before storing the schedule. A rejected request must neither allocate a saved schedule nor persist partial data. Successful saves return HTTP 201.
```

### pol_apply

`knowledge/confluence/controller-capacity-policy.md:28-30` (knowledge); SHA-256 `dee747968572194f8f5badee2a22e501e840ba51b6768084980693ed1ceffa0a`.

```text
## Applicability

Version 1.0 is approved and effective for the demo tickets dated after 2026-09-15. Historical ticket completion and customer expectations do not override these rules. This policy defines capacity; it does not authorize or prescribe a firmware upgrade.
```

### val_logic

`app/schedule_validator.py:24-28` (code); SHA-256 `3d9dc7751b8e8c98ad62c8d8f8d3a0bcb60ee5e551baf9c72189659c22517626`.

```text
    max_zones = MAX_ZONES
    if device["model"] == "PRO" and tuple(int(part) for part in firmware.split(".")) >= PRO_EXPANDED_FIRMWARE:
        max_zones = PRO_EXPANDED_MAX_ZONES
    if len(zones) > max_zones:
        return f"Controller supports at most {max_zones} zones"
```

### svc_flow

`app/schedule_service.py:24-30` (code); SHA-256 `3272360e047de58498ebbd2a143526362cd0325e386380eb9e4482141a0202de`.

```text
        device = self.registry.get(controller_id)
        if device is None:
            return ApiResponse(404, {"error": "Controller was not found", "code": "controller_not_found"})
        error = validate_zones(payload["zones"], device)
        if error is not None:
            code = "zone_limit_exceeded" if error.startswith("Controller supports at most ") else "validation_error"
            return self._invalid(error, code)
```

### ticket_rep

`knowledge/jira/AG-1424.md:11-17` (knowledge); SHA-256 `be5a02713e46cd368ae8f8aa03433a8cef78850eba04f213d90fa01aa6d26f42`.

```text
## Reported behavior

The customer reports that saving 30 zones on controller DEV-102 returns HTTP 400 with `zone_limit_exceeded`. Saving 20 zones on the same controller succeeds. The customer believes that every Pro controller should accept larger schedules.

## Reproduction

Use `controller_id: DEV-102` and zone IDs 1 through 30. Submit the schedule through the backend adapter. Record the response status and error code, then repeat with zone IDs 1 through 20. No model or firmware override is included in the request.
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

### ticket_triage

`knowledge/jira/AG-1424.md:19-21` (knowledge); SHA-256 `be5a02713e46cd368ae8f8aa03433a8cef78850eba04f213d90fa01aa6d26f42`.

```text
## Triage request

Determine the expected behavior for this device using its registry record and the applicable approved requirements. Do not treat the customer's assumption as an approved requirement. There is no confirmed diagnosis or approved firmware-upgrade procedure attached to this ticket.
```

### ag981_scope

`knowledge/jira/AG-981.md:12-14` (knowledge); SHA-256 `d737bc9999efb2ec5a6caccd6dccc99ec094c924f1cd160c3d9d2cfcabde0bed`.

```text
## Delivered scope

The schedule editor was updated to support selecting up to 50 zones for eligible Pro controllers. Eligibility and capacity are defined by the approved controller capacity policy. This ticket completed the frontend work only; completion does not establish that every backend path enforces the expanded policy.
```

### design_owner

`knowledge/confluence/schedule-validation-design.md:16-18` (knowledge); SHA-256 `059ef4a98a77b0383f396e87442d201e6664129b02d91cba47a822f8e46b45dc`.

```text
## Authority and ownership

Scheduling Backend owns schedule-save validation and the backend service. The device registry supplies model and firmware facts. The approved controller capacity policy supplies the business requirements. Frontend validation helps the user construct a request; the backend independently enforces those requirements.
```

