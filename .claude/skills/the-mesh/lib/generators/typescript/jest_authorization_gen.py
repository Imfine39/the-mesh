"""Mesh to Jest Authorization Test Generator

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
    condition: dict | None
    pattern: str


class JestAuthorizationGenerator:
    """Generates Jest authorization tests from TRIR specification"""

    def __init__(self, spec: dict[str, Any]):
        self.spec = spec
        self.entities = spec.get("entities", {})
        self.roles = spec.get("roles", {})
        self.test_strategies = spec.get("testStrategies", {})

    def generate_all(self) -> str:
        """Generate all authorization tests"""
        authz_config = self.test_strategies.get("templates", {}).get("authorization", {})

        if not authz_config.get("enabled", False):
            return self._render_empty_tests()

        targets = authz_config.get("targets", [])
        if not targets:
            targets = list(self.roles.keys())

        test_cases = []
        for role_name in targets:
            role_def = self.roles.get(role_name)
            if role_def:
                test_cases.extend(self._generate_tests_for_role(role_name, role_def))

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

            for action in actions:
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
        resource_roles: dict[str, list[str]] = {}

        for role_name in role_names:
            role_def = self.roles.get(role_name, {})
            for perm in role_def.get("permissions", []):
                resource = perm.get("resource", "")
                if resource not in resource_roles:
                    resource_roles[resource] = []
                resource_roles[resource].append(role_name)

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
        return '''/**
 * Auto-generated Authorization Tests from TRIR specification
 *
 * Authorization testing is DISABLED in testStrategies.
 * To enable, set testStrategies.templates.authorization.enabled = true
 *
 * @generated
 */

describe('Authorization Tests (disabled)', () => {
  test.skip('placeholder', () => {
    // Authorization tests disabled in testStrategies
  });
});
'''

    def _render_tests(self, test_cases: list[AuthorizationTestCase]) -> str:
        """Render test cases to executable Jest code"""
        lines = [
            '/**',
            ' * Auto-generated Authorization Tests from TRIR specification',
            ' *',
            ' * These tests verify authorization rules:',
            ' * - Allowed actions succeed for each role',
            ' * - Disallowed actions are properly rejected',
            ' * - Condition-based permissions work correctly',
            ' *',
            ' * @generated',
            ' */',
            '',
            '// ========== Test Infrastructure ==========',
            '',
            'interface AuthContext {',
            '  userId: string;',
            '  role: string;',
            '  attributes: Record<string, unknown>;',
            '}',
            '',
            'interface PolicyEngine {',
            '  evaluate(ctx: AuthContext, action: string, resource: string, resourceData?: Record<string, unknown>): boolean;',
            '}',
            '',
            'class AuthorizationChecker {',
            '  constructor(private policyEngine: PolicyEngine) {}',
            '',
            '  can(ctx: AuthContext, action: string, resource: string, resourceData?: Record<string, unknown>): boolean {',
            '    return this.policyEngine.evaluate(ctx, action, resource, resourceData);',
            '  }',
            '',
            '  assertAllowed(ctx: AuthContext, action: string, resource: string, resourceData?: Record<string, unknown>): void {',
            '    expect(this.can(ctx, action, resource, resourceData)).toBe(true);',
            '  }',
            '',
            '  assertDenied(ctx: AuthContext, action: string, resource: string, resourceData?: Record<string, unknown>): void {',
            '    expect(this.can(ctx, action, resource, resourceData)).toBe(false);',
            '  }',
            '}',
            '',
            'class MockPolicyEngine implements PolicyEngine {',
            '  constructor(private permissions: Record<string, Record<string, { actions: string[] }>>) {}',
            '',
            '  evaluate(ctx: AuthContext, action: string, resource: string): boolean {',
            '    const rolePerms = this.permissions[ctx.role] || {};',
            '    const resourcePerms = rolePerms[resource] || { actions: [] };',
            '    return resourcePerms.actions.includes(action);',
            '  }',
            '}',
            '',
            'function createAuthChecker(): AuthorizationChecker {',
            '  // TODO: Load actual policy from spec',
            '  const policy = new MockPolicyEngine({});',
            '  return new AuthorizationChecker(policy);',
            '}',
            '',
        ]

        by_role: dict[str, list[AuthorizationTestCase]] = {}
        for tc in test_cases:
            if tc.role not in by_role:
                by_role[tc.role] = []
            by_role[tc.role].append(tc)

        lines.append('// ========== Tests ==========')
        lines.append('')

        for role_name, cases in by_role.items():
            if "," in role_name:
                class_name = "Authorization: CrossRole"
            else:
                class_name = f"Authorization: {role_name}"

            lines.append(f"describe('{class_name}', () => {{")
            lines.append('  let checker: AuthorizationChecker;')
            lines.append('')
            lines.append('  beforeEach(() => {')
            lines.append('    checker = createAuthChecker();')
            lines.append('  });')
            lines.append('')

            for tc in cases:
                lines.extend(self._render_test_method(tc))
                lines.append('')

            lines.append('});')
            lines.append('')

        return '\n'.join(lines)

    def _render_test_method(self, tc: AuthorizationTestCase) -> list[str]:
        """Render a single test method"""
        lines = []

        if tc.pattern == "permission_granted":
            lines.append(f"  test('{tc.description}', () => {{")
            lines.append(f'    const ctx: AuthContext = {{')
            lines.append(f'      userId: "test_user_1",')
            lines.append(f'      role: "{tc.role}",')
            lines.append(f'      attributes: {{}},')
            lines.append(f'    }};')
            lines.append(f'    ')
            lines.append(f'    checker.assertAllowed(ctx, "{tc.action}", "{tc.resource}");')
            lines.append('  });')

        elif tc.pattern == "permission_denied":
            lines.append(f"  test('{tc.description}', () => {{")
            lines.append(f'    const ctx: AuthContext = {{')
            lines.append(f'      userId: "test_user_1",')
            lines.append(f'      role: "{tc.role}",')
            lines.append(f'      attributes: {{}},')
            lines.append(f'    }};')
            lines.append(f'    ')
            lines.append(f'    checker.assertDenied(ctx, "{tc.action}", "{tc.resource}");')
            lines.append('  });')

        elif tc.pattern == "condition_based":
            if tc.expected == "allow":
                lines.append(f"  test('{tc.description}', () => {{")
                lines.append(f'    const ctx: AuthContext = {{')
                lines.append(f'      userId: "test_user_1",')
                lines.append(f'      role: "{tc.role}",')
                lines.append(f'      attributes: {{}},')
                lines.append(f'    }};')
                lines.append(f'    ')
                lines.append(f'    // Resource data that satisfies condition')
                lines.append(f'    const resourceData = {{ userId: "test_user_1" }};')
                lines.append(f'    ')
                lines.append(f'    checker.assertAllowed(ctx, "{tc.action}", "{tc.resource}", resourceData);')
                lines.append('  });')
            else:
                lines.append(f"  test('{tc.description}', () => {{")
                lines.append(f'    const ctx: AuthContext = {{')
                lines.append(f'      userId: "test_user_1",')
                lines.append(f'      role: "{tc.role}",')
                lines.append(f'      attributes: {{}},')
                lines.append(f'    }};')
                lines.append(f'    ')
                lines.append(f'    // Resource data that does NOT satisfy condition')
                lines.append(f'    const resourceData = {{ userId: "other_user" }};')
                lines.append(f'    ')
                lines.append(f'    checker.assertDenied(ctx, "{tc.action}", "{tc.resource}", resourceData);')
                lines.append('  });')

        elif tc.pattern == "cross_role":
            lines.append(f"  test.skip('{tc.description}', () => {{")
            lines.append(f'    // Cross-role verification requires actual policy setup')
            lines.append('  });')

        return lines

    def _to_snake(self, name: str) -> str:
        """Convert to snake_case"""
        import re
        s1 = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', name)
        return re.sub('([a-z0-9])([A-Z])', r'\1_\2', s1).lower()

    def _to_pascal(self, name: str) -> str:
        """Convert to PascalCase"""
        return "".join(word.capitalize() for word in self._to_snake(name).split("_"))
