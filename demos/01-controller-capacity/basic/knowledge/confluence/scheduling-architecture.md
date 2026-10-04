# Scheduling Architecture

Synthetic demonstration fixture. This is not a DataHoney customer record.

Owner: Scheduling Backend
Responsibility: scheduling API orchestration, controller capabilities and validation.

The backend schedule-creation path is:
ScheduleController → ScheduleService → DeviceConfigurationService
→ ScheduleValidator → ScheduleRepository.

The controller in app/schedule_controller.py delegates create requests to
ScheduleService.create_schedule in app/schedule_service.py. The service first
asks ScheduleValidator to parse the request shape and selected controller.
Malformed requests return HTTP 400 before capabilities are resolved.

DeviceConfigurationService in app/device_configuration_service.py resolves
the maximum zone count from the capability table. Its default family is Legacy
for callers that do not specify a controller. ScheduleValidator in
app/schedule_validator.py then applies the maximum to the parsed schedule.
Only successful validation reaches ScheduleRepository.save in
app/schedule_repository.py.

The repository is in-memory storage scoped to its instance. There is no database,
network dependency or durable persistence in this practice application.
Successful creates return HTTP 201 and an assigned schedule ID. Reads through
the controller and service return a copy of the stored schedule, or HTTP 404.
Rejected creates never allocate an ID or write a schedule.

Frontend editor changes do not automatically change backend capability
resolution. Consult Scheduling Backend for server validation and capacity
questions. No individual engineer or escalation contact is recorded here.

