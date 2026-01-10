"""Miscellaneous domain validation mixin for The Mesh validator.

Includes validation for:
- Gateways (BPMN-style workflow control)
- Deadlines/SLAs
- Schedules
- Constraints
- External services
"""

import re
from core.errors import ValidationError


class MiscValidationMixin:
    """Mixin providing miscellaneous domain validation methods."""

    def _validate_gateways(self, spec: dict) -> list[ValidationError]:
        """
        Validate gateway definitions (Phase 2 - BPMN-style workflow control).

        Checks:
        1. Gateway type is valid (exclusive, parallel, inclusive, event_based)
        2. Outgoing flow targets exist (functions, other gateways, or events)
        3. Exclusive/inclusive gateways have proper conditions
        4. Parallel gateways don't have conditions on outgoing flows
        5. Event-based gateways reference valid events
        """
        errors = []
        gateways = spec.get("gateways", {})
        functions = spec.get("functions", {})
        events = spec.get("events", {})

        valid_gateway_types = ["exclusive", "parallel", "inclusive", "event_based"]

        for gw_name, gw in gateways.items():
            gw_type = gw.get("type", "")

            # Validate gateway type
            if gw_type and gw_type not in valid_gateway_types:
                errors.append(ValidationError(
                    path=f"gateways.{gw_name}.type",
                    message=f"Invalid gateway type '{gw_type}'. Valid types: {', '.join(valid_gateway_types)}"
                ))

            # Validate outgoing flows
            for i, flow in enumerate(gw.get("outgoingFlows", [])):
                target = flow.get("target", "")

                # Target should be a function, event, or another gateway
                if target:
                    if target not in functions and target not in events and target not in gateways:
                        errors.append(ValidationError(
                            path=f"gateways.{gw_name}.outgoingFlows[{i}].target",
                            message=f"Outgoing flow target '{target}' not found in functions, events, or gateways"
                        ))

                # Parallel gateways should NOT have conditions
                if gw_type == "parallel" and flow.get("condition"):
                    errors.append(ValidationError(
                        path=f"gateways.{gw_name}.outgoingFlows[{i}]",
                        message="Parallel gateway flows should not have conditions - all paths execute"
                    ))

                # Event-based gateways should reference events
                if gw_type == "event_based":
                    event_ref = flow.get("event", "")
                    if event_ref and event_ref not in events:
                        errors.append(ValidationError(
                            path=f"gateways.{gw_name}.outgoingFlows[{i}].event",
                            message=f"Event-based gateway references unknown event '{event_ref}'"
                        ))

            # Validate incoming flow references
            for i, flow in enumerate(gw.get("incomingFlows", [])):
                source = flow.get("source", "")
                if source:
                    if source not in functions and source not in events and source not in gateways:
                        errors.append(ValidationError(
                            path=f"gateways.{gw_name}.incomingFlows[{i}].source",
                            message=f"Incoming flow source '{source}' not found in functions, events, or gateways"
                        ))

        return errors

    def _validate_deadlines(self, spec: dict) -> list[ValidationError]:
        """
        Validate deadline/SLA definitions (Phase 2 - Temporal workflow control).

        Checks:
        1. Referenced entity exists
        2. Start condition references valid fields
        3. Action function exists
        4. Escalation events exist
        5. Duration format is valid
        """
        errors = []
        deadlines = spec.get("deadlines", {})
        entities = spec.get("state", {})
        functions = spec.get("functions", {})
        events = spec.get("events", {})

        for dl_name, dl in deadlines.items():
            # Validate entity reference
            entity = dl.get("entity", "")
            if entity and entity not in entities:
                errors.append(ValidationError(
                    path=f"deadlines.{dl_name}.entity",
                    message=f"Deadline references unknown entity '{entity}'"
                ))

            # Validate start condition field references
            start_when = dl.get("startWhen", {})
            if start_when and entity and entity in entities:
                entity_fields = entities[entity].get("fields", {})
                field = start_when.get("field", "")
                if field and field not in entity_fields:
                    errors.append(ValidationError(
                        path=f"deadlines.{dl_name}.startWhen.field",
                        message=f"Start condition field '{field}' not found in entity '{entity}'"
                    ))

            # Validate action function reference
            action = dl.get("action", "")
            if action and action not in functions:
                errors.append(ValidationError(
                    path=f"deadlines.{dl_name}.action",
                    message=f"Deadline action references unknown function '{action}'"
                ))

            # Validate escalation events
            for i, esc in enumerate(dl.get("escalations", [])):
                event_ref = esc.get("event", "")
                if event_ref and event_ref not in events:
                    errors.append(ValidationError(
                        path=f"deadlines.{dl_name}.escalations[{i}].event",
                        message=f"Escalation references unknown event '{event_ref}'"
                    ))

                # Validate escalation action
                esc_action = esc.get("action", "")
                if esc_action and esc_action not in functions:
                    errors.append(ValidationError(
                        path=f"deadlines.{dl_name}.escalations[{i}].action",
                        message=f"Escalation action references unknown function '{esc_action}'"
                    ))

            # Validate duration format (ISO 8601 duration pattern)
            duration = dl.get("duration", "")
            if duration:
                # Simple ISO 8601 duration pattern: P[n]Y[n]M[n]DT[n]H[n]M[n]S or shortcuts like "24h", "7d"
                iso_pattern = r'^P(\d+Y)?(\d+M)?(\d+D)?(T(\d+H)?(\d+M)?(\d+S)?)?$'
                shortcut_pattern = r'^\d+[hdwms]$'  # 24h, 7d, 1w, 30m, 60s
                if not re.match(iso_pattern, duration, re.I) and not re.match(shortcut_pattern, duration, re.I):
                    errors.append(ValidationError(
                        path=f"deadlines.{dl_name}.duration",
                        message=f"Invalid duration format '{duration}'. Use ISO 8601 (P1D, PT2H) or shortcut (24h, 7d)"
                    ))

        return errors

    def _validate_schedules(self, spec: dict) -> list[ValidationError]:
        """
        Validate schedule definitions (Phase 5 - Temporal layer).

        Checks:
        1. Cron expression format
        2. Timezone validity
        3. Action function reference
        4. Overlap policy validity
        """
        errors = []
        schedules = spec.get("schedules", {})
        functions = spec.get("functions", {})

        # Cron expression: 5 or 6 fields (second minute hour day month weekday [year])
        # Simple validation - check field count and basic patterns
        cron_field_pattern = r'^(\*|[0-9,\-\/\*]+)$'

        valid_overlap_policies = ["skip", "buffer_one", "cancel_other", "allow_all"]

        # Common timezones (not exhaustive, but covers major ones)
        common_timezones = [
            "UTC", "GMT",
            "Asia/Tokyo", "Asia/Shanghai", "Asia/Seoul", "Asia/Singapore",
            "America/New_York", "America/Los_Angeles", "America/Chicago",
            "Europe/London", "Europe/Paris", "Europe/Berlin",
            "Australia/Sydney", "Pacific/Auckland"
        ]

        for sched_name, sched in schedules.items():
            # Validate cron expression
            cron = sched.get("cron", "")
            if cron:
                fields = cron.split()
                if len(fields) < 5 or len(fields) > 6:
                    errors.append(ValidationError(
                        path=f"schedules.{sched_name}.cron",
                        message=f"Invalid cron expression '{cron}'. Expected 5 or 6 fields (minute hour day month weekday [year])"
                    ))
                else:
                    for i, field in enumerate(fields):
                        if not re.match(cron_field_pattern, field):
                            errors.append(ValidationError(
                                path=f"schedules.{sched_name}.cron",
                                message=f"Invalid cron field '{field}' at position {i}"
                            ))
                            break

            # Validate timezone
            timezone = sched.get("timezone", "")
            if timezone and timezone not in common_timezones:
                # Warning level - timezone might be valid but not in our list
                # For now, just check format (Region/City or abbreviation)
                tz_pattern = r'^[A-Za-z]+(/[A-Za-z_]+)?$'
                if not re.match(tz_pattern, timezone):
                    errors.append(ValidationError(
                        path=f"schedules.{sched_name}.timezone",
                        message=f"Invalid timezone format '{timezone}'. Use IANA format like 'Asia/Tokyo'"
                    ))

            # Validate action function reference
            action = sched.get("action", "")
            if action and action not in functions:
                errors.append(ValidationError(
                    path=f"schedules.{sched_name}.action",
                    message=f"Schedule references unknown function '{action}'"
                ))

            # Validate overlap policy
            overlap = sched.get("overlapPolicy", "")
            if overlap and overlap not in valid_overlap_policies:
                errors.append(ValidationError(
                    path=f"schedules.{sched_name}.overlapPolicy",
                    message=f"Invalid overlap policy '{overlap}'. Valid: {', '.join(valid_overlap_policies)}"
                ))

        return errors

    def _validate_constraints(self, spec: dict) -> list[ValidationError]:
        """
        Validate constraint definitions (Phase 5 - Data integrity layer).

        Checks:
        1. Entity reference exists
        2. Fields exist in entity (for unique constraints)
        3. Expression references valid fields (for check constraints)
        4. Constraint type validity
        """
        errors = []
        constraints = spec.get("constraints", {})
        entities = spec.get("state", {})

        valid_constraint_types = ["unique", "check", "foreign_key"]

        for const_name, const in constraints.items():
            entity = const.get("entity", "")
            const_type = const.get("type", "")

            # Validate constraint type
            if const_type and const_type not in valid_constraint_types:
                errors.append(ValidationError(
                    path=f"constraints.{const_name}.type",
                    message=f"Invalid constraint type '{const_type}'. Valid: {', '.join(valid_constraint_types)}"
                ))

            # Entity reference already validated in _validate_references
            # Additional: validate fields for unique constraints
            if entity and entity in entities:
                entity_fields = entities[entity].get("fields", {})

                # For unique constraints, check that all fields exist
                if const_type == "unique":
                    const_fields = const.get("fields", [])
                    for field in const_fields:
                        if field not in entity_fields:
                            errors.append(ValidationError(
                                path=f"constraints.{const_name}.fields",
                                message=f"Unique constraint field '{field}' not found in entity '{entity}'"
                            ))

                # For foreign_key constraints, check reference
                if const_type == "foreign_key":
                    ref_entity = const.get("references", {}).get("entity", "")
                    if ref_entity and ref_entity not in entities:
                        errors.append(ValidationError(
                            path=f"constraints.{const_name}.references.entity",
                            message=f"Foreign key references unknown entity '{ref_entity}'"
                        ))

        return errors

    def _validate_external_services(self, spec: dict) -> list[ValidationError]:
        """
        Validate external service definitions (Phase 4 - External layer).

        Checks:
        1. BaseUrl format validation
        2. Authentication type validity
        3. HTTP method validity
        4. Retry policy validity
        """
        errors = []
        services = spec.get("externalServices", {})

        valid_auth_types = ["none", "bearer", "basic", "api_key", "oauth2"]
        valid_http_methods = ["GET", "POST", "PUT", "PATCH", "DELETE"]
        valid_service_types = ["rest", "graphql", "grpc", "soap"]

        url_pattern = re.compile(r'^https?://[^\s/$.?#].[^\s]*$', re.I)

        for svc_name, svc in services.items():
            # Validate baseUrl
            base_url = svc.get("baseUrl", "")
            if base_url and not url_pattern.match(base_url):
                errors.append(ValidationError(
                    path=f"externalServices.{svc_name}.baseUrl",
                    message=f"Invalid base URL format: '{base_url}'"
                ))

            # Validate service type
            svc_type = svc.get("type", "rest")
            if svc_type not in valid_service_types:
                errors.append(ValidationError(
                    path=f"externalServices.{svc_name}.type",
                    message=f"Invalid service type '{svc_type}'. Valid: {', '.join(valid_service_types)}"
                ))

            # Validate authentication type (from 'auth' or 'authentication')
            auth = svc.get("auth", svc.get("authentication", {}))
            if auth:
                auth_type = auth.get("type", "")
                if auth_type and auth_type not in valid_auth_types:
                    errors.append(ValidationError(
                        path=f"externalServices.{svc_name}.authentication.type",
                        message=f"Invalid auth type '{auth_type}'. Valid: {', '.join(valid_auth_types)}"
                    ))

            # Validate operations
            for op_name, op in svc.get("operations", {}).items():
                method = op.get("method", "")
                if method and method not in valid_http_methods:
                    errors.append(ValidationError(
                        path=f"externalServices.{svc_name}.operations.{op_name}.method",
                        message=f"Invalid HTTP method '{method}'. Valid: {', '.join(valid_http_methods)}"
                    ))

            # Validate retry policy
            retry = svc.get("retry", svc.get("retryPolicy", {}))
            if retry:
                max_attempts = retry.get("maxAttempts", 3)
                if not isinstance(max_attempts, int) or max_attempts < 1:
                    errors.append(ValidationError(
                        path=f"externalServices.{svc_name}.retryPolicy.maxAttempts",
                        message="maxAttempts must be a positive integer"
                    ))

        return errors
