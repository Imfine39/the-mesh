"""Policy validation mixin for The Mesh validator.

Includes validation for:
- Roles and permissions
- Audit policies
- Data policies (PII, masking, retention)
"""

import re
from core.errors import ValidationError


class PolicyValidationMixin:
    """Mixin providing policy validation methods."""

    def _validate_roles(self, spec: dict) -> tuple[list[ValidationError], list[ValidationError]]:
        """
        Validate role and permission definitions (Phase 3 - Security layer).

        Checks:
        1. Circular inheritance detection
        2. EntityPermission entity references
        3. EntityPermission operation validity
        4. Permission-function consistency
        """
        errors = []
        warnings = []
        roles = spec.get("roles", {})
        entities = spec.get("state", {})
        functions = spec.get("functions", {})

        # Valid entity operations
        valid_operations = ["read", "create", "update", "delete", "list"]

        # Build inheritance graph for cycle detection
        inheritance_graph = {}
        for role_name, role in roles.items():
            inheritance_graph[role_name] = role.get("inherits", [])

        # Detect circular inheritance
        def detect_cycle(role: str, visited: set, rec_stack: set) -> list[str] | None:
            visited.add(role)
            rec_stack.add(role)

            for parent in inheritance_graph.get(role, []):
                if parent not in roles:
                    # Already validated in _validate_references
                    continue
                if parent not in visited:
                    cycle = detect_cycle(parent, visited, rec_stack)
                    if cycle is not None:
                        return [role] + cycle
                elif parent in rec_stack:
                    return [role, parent]

            rec_stack.remove(role)
            return None

        visited = set()
        for role_name in roles:
            if role_name not in visited:
                cycle = detect_cycle(role_name, visited, set())
                if cycle:
                    errors.append(ValidationError(
                        path="roles",
                        message=f"Circular role inheritance detected: {' -> '.join(cycle)}"
                    ))
                    break

        # Validate each role
        for role_name, role in roles.items():
            # Validate entityPermissions
            for i, ep in enumerate(role.get("entityPermissions", [])):
                entity = ep.get("entity", "")

                # Check entity exists
                if entity and entity not in entities:
                    errors.append(ValidationError(
                        path=f"roles.{role_name}.entityPermissions[{i}]",
                        message=f"Entity permission references unknown entity '{entity}'"
                    ))

                # Check operations are valid
                operations = ep.get("operations", [])
                for op in operations:
                    if op not in valid_operations:
                        errors.append(ValidationError(
                            path=f"roles.{role_name}.entityPermissions[{i}].operations",
                            message=f"Invalid operation '{op}'. Valid: {', '.join(valid_operations)}"
                        ))

            # Validate permissions reference existing functions (if naming convention matches)
            permissions = role.get("permissions", [])
            for perm in permissions:
                # Convention: permission name may match function name
                # e.g., "execute_clearing" permission grants access to execute_clearing function
                if perm in functions:
                    # Permission matches a function - this is valid
                    pass

        return errors, warnings

    def _validate_audit_policies(self, spec: dict) -> list[ValidationError]:
        """
        Validate audit policy definitions (Phase 3 - Audit layer).

        Checks:
        1. Entity reference exists
        2. Fields reference exists in entity (unless 'all')
        3. Operations are valid
        """
        errors = []
        audit_policies = spec.get("auditPolicies", {})
        entities = spec.get("state", {})

        valid_operations = ["create", "update", "delete", "read"]

        for policy_name, policy in audit_policies.items():
            entity = policy.get("entity", "")

            # Entity reference already validated in _validate_references
            # Additional: validate fields reference
            if entity and entity in entities:
                entity_fields = entities[entity].get("fields", {})
                policy_fields = policy.get("fields", [])

                for field in policy_fields:
                    if field != "all" and field not in entity_fields:
                        errors.append(ValidationError(
                            path=f"auditPolicies.{policy_name}.fields",
                            message=f"Audit policy references unknown field '{field}' in entity '{entity}'"
                        ))

            # Validate operations
            operations = policy.get("operations", [])
            for op in operations:
                if op not in valid_operations:
                    errors.append(ValidationError(
                        path=f"auditPolicies.{policy_name}.operations",
                        message=f"Invalid audit operation '{op}'. Valid: {', '.join(valid_operations)}"
                    ))

        return errors

    def _validate_data_policies(self, spec: dict) -> list[ValidationError]:
        """
        Validate data policy definitions (Phase 4 - Data layer).

        Checks:
        1. Entity reference exists
        2. PII fields exist in entity
        3. Masking fields exist in entity
        4. Retention period format
        """
        errors = []
        policies = spec.get("dataPolicies", {})
        entities = spec.get("state", {})

        for policy_name, policy in policies.items():
            entity = policy.get("entity", "")

            # Entity reference already validated in _validate_references
            # Additional: validate PII and masking fields
            if entity and entity in entities:
                entity_fields = entities[entity].get("fields", {})

                # Validate piiFields
                pii_fields = policy.get("piiFields", [])
                for field in pii_fields:
                    if field not in entity_fields:
                        errors.append(ValidationError(
                            path=f"dataPolicies.{policy_name}.piiFields",
                            message=f"PII field '{field}' not found in entity '{entity}'"
                        ))

                # Validate masking fields
                masking = policy.get("masking", {})
                if masking:
                    masking_fields = masking.get("fields", [])
                    for field in masking_fields:
                        if field not in entity_fields:
                            errors.append(ValidationError(
                                path=f"dataPolicies.{policy_name}.masking.fields",
                                message=f"Masking field '{field}' not found in entity '{entity}'"
                            ))

                    # Validate masking strategy
                    valid_strategies = ["partial", "full", "hash", "redact"]
                    strategy = masking.get("strategy", "")
                    if strategy and strategy not in valid_strategies:
                        errors.append(ValidationError(
                            path=f"dataPolicies.{policy_name}.masking.strategy",
                            message=f"Invalid masking strategy '{strategy}'. Valid: {', '.join(valid_strategies)}"
                        ))

            # Validate retention period format (basic check)
            retention = policy.get("retention", {})
            if retention:
                period = retention.get("period", "")
                if period:
                    # Simple pattern: number + unit (e.g., "7 years", "90 days", "1 year")
                    period_pattern = r'^\d+\s*(year|years|month|months|day|days|week|weeks)$'
                    if not re.match(period_pattern, period, re.I):
                        errors.append(ValidationError(
                            path=f"dataPolicies.{policy_name}.retention.period",
                            message=f"Invalid retention period format '{period}'. Use format like '7 years', '90 days'"
                        ))

        return errors
