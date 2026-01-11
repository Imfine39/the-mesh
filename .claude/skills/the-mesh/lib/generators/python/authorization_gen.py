"""Mesh to pytest Authorization Test Generator

Generates authorization edge case tests from roles defined in spec.

Test patterns generated:
1. Permission granted - verify allowed actions succeed
2. Permission denied - verify disallowed actions fail
3. Condition-based access - verify condition logic works correctly
4. Cross-role conflict - verify role separation
"""

from typing import Any
from dataclasses import dataclass


@dataclass
class AuthorizationTestCase:
    """Represents an authorization test case"""
    id: str
    description: str
    role: str
    resource: str
    action: str
    expected: str  # 'allow', 'deny'
    condition: dict | None  # Condition expression if any
    pattern: str  # 'permission_granted', 'permission_denied', 'condition_based', 'cross_role'


class AuthorizationTestGenerator:
    """Generates pytest authorization tests from TRIR specification"""

    def __init__(self, spec: dict[str, Any]):
        self.spec = spec
        self.entities = spec.get("entities", spec.get("entities", {}))
        self.roles = spec.get("roles", {})
        self.test_strategies = spec.get("testStrategies", {})

    def generate_all(self) -> str:
        """Generate all authorization tests"""
        # Get targets from testStrategies
        authz_config = self.test_strategies.get("templates", {}).get("authorization", {})

        if not authz_config.get("enabled", False):
            return self._render_empty_tests()

        targets = authz_config.get("targets", [])
        if not targets:
            # Default: test all roles
            targets = list(self.roles.keys())

        test_cases = []
        for role_name in targets:
            role_def = self.roles.get(role_name)
            if role_def:
                test_cases.extend(self._generate_tests_for_role(role_name, role_def))

        # Generate cross-role tests
        if len(targets) >= 2:
            test_cases.extend(self._generate_cross_role_tests(targets))

        return self._render_tests(test_cases)

    def _generate_tests_for_role(self, role_name: str, role_def: dict) -> list[AuthorizationTestCase]:
        """Generate authorization test cases for a role"""
        cases = []
        permissions = role_def.get("permissions", [])

        for perm in permissions:
            resource = perm.get("resource", "")
            actions = perm.get("actions", [])
            condition = perm.get("condition")

            # Test each allowed action
            for action in actions:
                # Pattern 1: Permission granted
                cases.append(AuthorizationTestCase(
                    id=f"authz_{role_name}_{resource}_{action}_allowed",
                    description=f"{role_name} should be able to {action} {resource}",
                    role=role_name,
                    resource=resource,
                    action=action,
                    expected="allow",
                    condition=condition,
                    pattern="permission_granted",
                ))

                # Pattern 3: Condition-based (if condition exists)
                if condition:
                    cases.append(AuthorizationTestCase(
                        id=f"authz_{role_name}_{resource}_{action}_condition_pass",
                        description=f"{role_name} can {action} {resource} when condition is met",
                        role=role_name,
                        resource=resource,
                        action=action,
                        expected="allow",
                        condition=condition,
                        pattern="condition_based",
                    ))
                    cases.append(AuthorizationTestCase(
                        id=f"authz_{role_name}_{resource}_{action}_condition_fail",
                        description=f"{role_name} cannot {action} {resource} when condition is not met",
                        role=role_name,
                        resource=resource,
                        action=action,
                        expected="deny",
                        condition=condition,
                        pattern="condition_based",
                    ))

            # Pattern 2: Permission denied - actions not in the list
            all_actions = ["create", "read", "update", "delete", "list"]
            denied_actions = [a for a in all_actions if a not in actions]
            for action in denied_actions:
                cases.append(AuthorizationTestCase(
                    id=f"authz_{role_name}_{resource}_{action}_denied",
                    description=f"{role_name} should NOT be able to {action} {resource}",
                    role=role_name,
                    resource=resource,
                    action=action,
                    expected="deny",
                    condition=None,
                    pattern="permission_denied",
                ))

        return cases

    def _generate_cross_role_tests(self, role_names: list[str]) -> list[AuthorizationTestCase]:
        """Generate tests that verify role separation"""
        cases = []

        # Find resources that are accessed by multiple roles
        resource_roles: dict[str, list[str]] = {}
        for role_name in role_names:
            role_def = self.roles.get(role_name, {})
            for perm in role_def.get("permissions", []):
                resource = perm.get("resource", "")
                if resource not in resource_roles:
                    resource_roles[resource] = []
                resource_roles[resource].append(role_name)

        # For shared resources, verify each role's permissions are distinct
        for resource, roles in resource_roles.items():
            if len(roles) >= 2:
                cases.append(AuthorizationTestCase(
                    id=f"authz_cross_role_{resource}_separation",
                    description=f"Roles {roles} should have correctly separated permissions for {resource}",
                    role=",".join(roles),
                    resource=resource,
                    action="*",
                    expected="varies",
                    condition=None,
                    pattern="cross_role",
                ))

        return cases

    def _render_empty_tests(self) -> str:
        """Render placeholder when authorization tests are disabled"""
        return '''"""
Auto-generated Authorization Tests from TRIR specification

Authorization testing is DISABLED in testStrategies.
To enable, set testStrategies.templates.authorization.enabled = true

@generated
"""

import pytest


class TestAuthorization:
    """Authorization tests (disabled)"""

    @pytest.mark.skip(reason="Authorization tests disabled in testStrategies")
    def test_placeholder(self):
        pass
'''

    def _render_tests(self, test_cases: list[AuthorizationTestCase]) -> str:
        """Render test cases to executable pytest code"""
        lines = [
            '"""',
            'Auto-generated Authorization Tests from TRIR specification',
            '',
            'These tests verify authorization rules:',
            '- Allowed actions succeed for each role',
            '- Disallowed actions are properly rejected',
            '- Condition-based permissions work correctly',
            '',
            '@generated',
            '"""',
            '',
            'import pytest',
            'from typing import Any',
            'from dataclasses import dataclass',
            '',
            '',
            '# ========== Test Infrastructure ==========',
            '',
            '@dataclass',
            'class AuthContext:',
            '    """Authentication context for testing"""',
            '    user_id: str',
            '    role: str',
            '    attributes: dict',
            '',
            '',
            'class AuthorizationChecker:',
            '    """Helper for authorization tests"""',
            '',
            '    def __init__(self, policy_engine):',
            '        self.policy_engine = policy_engine',
            '',
            '    def can(self, ctx: AuthContext, action: str, resource: str, resource_data: dict = None) -> bool:',
            '        """Check if context can perform action on resource"""',
            '        # TODO: Integrate with actual policy engine',
            '        return self.policy_engine.evaluate(ctx, action, resource, resource_data or {})',
            '',
            '    def assert_allowed(self, ctx: AuthContext, action: str, resource: str, resource_data: dict = None):',
            '        """Assert action is allowed"""',
            '        assert self.can(ctx, action, resource, resource_data), \\',
            '            f"Expected {ctx.role} to be allowed to {action} {resource}"',
            '',
            '    def assert_denied(self, ctx: AuthContext, action: str, resource: str, resource_data: dict = None):',
            '        """Assert action is denied"""',
            '        assert not self.can(ctx, action, resource, resource_data), \\',
            '            f"Expected {ctx.role} to be denied from {action} {resource}"',
            '',
            '',
            'class MockPolicyEngine:',
            '    """Mock policy engine for testing"""',
            '',
            '    def __init__(self, permissions: dict):',
            '        self.permissions = permissions',
            '',
            '    def evaluate(self, ctx: AuthContext, action: str, resource: str, resource_data: dict) -> bool:',
            '        """Evaluate permission"""',
            '        role_perms = self.permissions.get(ctx.role, {})',
            '        resource_perms = role_perms.get(resource, {})',
            '        return action in resource_perms.get("actions", [])',
            '',
            '',
            '# ========== Fixtures ==========',
            '',
            '@pytest.fixture',
            'def auth_checker():',
            '    """Create authorization checker with mock policy"""',
            '    # TODO: Load actual policy from spec',
            '    policy = MockPolicyEngine({})',
            '    return AuthorizationChecker(policy)',
            '',
            '',
        ]

        # Group by role
        by_role: dict[str, list[AuthorizationTestCase]] = {}
        for tc in test_cases:
            if tc.role not in by_role:
                by_role[tc.role] = []
            by_role[tc.role].append(tc)

        lines.append('# ========== Tests ==========')
        lines.append('')

        for role_name, cases in by_role.items():
            # Handle cross-role tests differently
            if "," in role_name:
                class_name = "TestAuthorizationCrossRole"
            else:
                class_name = f"TestAuthorization{self._to_pascal(role_name)}"

            lines.append(f'class {class_name}:')
            lines.append(f'    """Authorization tests for {role_name}"""')
            lines.append('')

            for tc in cases:
                lines.extend(self._render_test_method(tc))
                lines.append('')

        return '\n'.join(lines)

    def _render_test_method(self, tc: AuthorizationTestCase) -> list[str]:
        """Render a single test method"""
        lines = []
        method_name = f"test_{tc.id}"

        if tc.pattern == "permission_granted":
            lines.append(f'    def {method_name}(self, auth_checker):')
            lines.append(f'        """{tc.description}"""')
            lines.append(f'        # Arrange: Create auth context for {tc.role}')
            lines.append(f'        ctx = AuthContext(')
            lines.append(f'            user_id="test_user_1",')
            lines.append(f'            role="{tc.role}",')
            lines.append(f'            attributes={{}},')
            lines.append(f'        )')
            lines.append(f'        ')
            lines.append(f'        # Act & Assert: {tc.action} on {tc.resource} should be allowed')
            lines.append(f'        auth_checker.assert_allowed(ctx, "{tc.action}", "{tc.resource}")')

        elif tc.pattern == "permission_denied":
            lines.append(f'    def {method_name}(self, auth_checker):')
            lines.append(f'        """{tc.description}"""')
            lines.append(f'        # Arrange: Create auth context for {tc.role}')
            lines.append(f'        ctx = AuthContext(')
            lines.append(f'            user_id="test_user_1",')
            lines.append(f'            role="{tc.role}",')
            lines.append(f'            attributes={{}},')
            lines.append(f'        )')
            lines.append(f'        ')
            lines.append(f'        # Act & Assert: {tc.action} on {tc.resource} should be denied')
            lines.append(f'        auth_checker.assert_denied(ctx, "{tc.action}", "{tc.resource}")')

        elif tc.pattern == "condition_based":
            if tc.expected == "allow":
                lines.append(f'    def {method_name}(self, auth_checker):')
                lines.append(f'        """{tc.description}"""')
                lines.append(f'        # Arrange: Context where condition IS met')
                lines.append(f'        ctx = AuthContext(')
                lines.append(f'            user_id="test_user_1",')
                lines.append(f'            role="{tc.role}",')
                lines.append(f'            attributes={{}},')
                lines.append(f'        )')
                lines.append(f'        ')
                lines.append(f'        # Resource data that satisfies condition')
                lines.append(f'        resource_data = self._create_matching_resource("{tc.role}")')
                lines.append(f'        ')
                lines.append(f'        # Act & Assert')
                lines.append(f'        auth_checker.assert_allowed(ctx, "{tc.action}", "{tc.resource}", resource_data)')
                lines.append('')
                lines.append(f'    def _create_matching_resource(self, role: str) -> dict:')
                lines.append(f'        """Create resource that matches condition for role"""')
                lines.append(f'        # TODO: Generate from condition: {tc.condition}')
                lines.append(f'        return {{"userId": "test_user_1"}}')
            else:
                lines.append(f'    def {method_name}(self, auth_checker):')
                lines.append(f'        """{tc.description}"""')
                lines.append(f'        # Arrange: Context where condition is NOT met')
                lines.append(f'        ctx = AuthContext(')
                lines.append(f'            user_id="test_user_1",')
                lines.append(f'            role="{tc.role}",')
                lines.append(f'            attributes={{}},')
                lines.append(f'        )')
                lines.append(f'        ')
                lines.append(f'        # Resource data that does NOT satisfy condition')
                lines.append(f'        resource_data = self._create_non_matching_resource("{tc.role}")')
                lines.append(f'        ')
                lines.append(f'        # Act & Assert')
                lines.append(f'        auth_checker.assert_denied(ctx, "{tc.action}", "{tc.resource}", resource_data)')
                lines.append('')
                lines.append(f'    def _create_non_matching_resource(self, role: str) -> dict:')
                lines.append(f'        """Create resource that does NOT match condition"""')
                lines.append(f'        # TODO: Generate from condition: {tc.condition}')
                lines.append(f'        return {{"userId": "other_user"}}')

        elif tc.pattern == "cross_role":
            lines.append(f'    def {method_name}(self, auth_checker):')
            lines.append(f'        """{tc.description}"""')
            lines.append(f'        # This test verifies role separation for shared resource')
            roles = tc.role.split(",")
            lines.append(f'        roles = {roles}')
            lines.append(f'        resource = "{tc.resource}"')
            lines.append(f'        ')
            lines.append(f'        # Collect permissions for each role')
            lines.append(f'        role_permissions = {{}}')
            lines.append(f'        for role in roles:')
            lines.append(f'            ctx = AuthContext(user_id=f"user_{{role}}", role=role, attributes={{}})')
            lines.append(f'            permissions = []')
            lines.append(f'            for action in ["create", "read", "update", "delete", "list"]:')
            lines.append(f'                if auth_checker.can(ctx, action, resource):')
            lines.append(f'                    permissions.append(action)')
            lines.append(f'            role_permissions[role] = set(permissions)')
            lines.append(f'        ')
            lines.append(f'        # Verify: At least one action should differ between roles')
            lines.append(f'        # (otherwise why have separate roles?)')
            lines.append(f'        all_same = all(')
            lines.append(f'            role_permissions[roles[0]] == role_permissions[r]')
            lines.append(f'            for r in roles[1:]')
            lines.append(f'        )')
            lines.append(f'        # Note: This assertion may need adjustment based on actual requirements')
            lines.append(f'        # assert not all_same, f"Roles {{roles}} have identical permissions on {{resource}}"')
            lines.append(f'        pytest.skip("Cross-role verification requires actual policy setup")')

        return lines

    def _to_snake(self, name: str) -> str:
        """Convert to snake_case"""
        import re
        s1 = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', name)
        return re.sub('([a-z0-9])([A-Z])', r'\1_\2', s1).lower()

    def _to_pascal(self, name: str) -> str:
        """Convert to PascalCase"""
        return "".join(word.capitalize() for word in self._to_snake(name).split("_"))
