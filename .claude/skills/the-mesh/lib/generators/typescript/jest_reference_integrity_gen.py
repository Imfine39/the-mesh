"""Mesh to Jest Reference Integrity Test Generator

Generates tests for referential integrity constraints.

Test patterns generated:
1. Valid reference - reference to existing entity succeeds
2. Invalid reference - reference to non-existent entity fails
3. Cascade delete - deleting parent handles children correctly
4. Orphan prevention - cannot create child without valid parent
5. Reference update - updating reference validates new target
"""

from typing import Any
from dataclasses import dataclass


@dataclass
class ReferenceTestCase:
    """Represents a reference integrity test case"""
    id: str
    description: str
    source_entity: str
    source_field: str
    target_entity: str
    pattern: str  # 'valid_ref', 'invalid_ref', 'cascade_delete', 'orphan_prevention', 'ref_update'
    is_required: bool


class JestReferenceIntegrityGenerator:
    """Generates Jest reference integrity tests from TRIR specification"""

    def __init__(self, spec: dict[str, Any]):
        self.spec = spec
        self.entities = spec.get("entities", {})
        self.commands = spec.get("commands", {})
        self.relations = spec.get("relations", {})

    def generate_all(self) -> str:
        """Generate all reference integrity tests"""
        # Find all reference fields
        references = self._find_all_references()

        if not references:
            return self._render_empty_tests()

        test_cases = []
        for ref in references:
            test_cases.extend(self._generate_tests_for_reference(ref))

        return self._render_tests(test_cases)

    def _find_all_references(self) -> list[dict]:
        """Find all reference fields across entities"""
        references = []
        seen = set()  # Avoid duplicates

        for entity_name, entity_def in self.entities.items():
            fields = entity_def.get("fields", {})
            parent = entity_def.get("parent")

            for field_name, field_def in fields.items():
                ref_target = None

                # Check for ref type at field level
                if field_def.get("ref"):
                    ref_target = field_def.get("ref")

                # Check for type: { ref: Entity } format (TRIR format)
                field_type = field_def.get("type")
                if isinstance(field_type, dict) and field_type.get("ref"):
                    ref_target = field_type.get("ref")

                if ref_target:
                    key = (entity_name, field_name, ref_target)
                    if key not in seen:
                        seen.add(key)
                        references.append({
                            "source_entity": entity_name,
                            "source_field": field_name,
                            "target_entity": ref_target,
                            "required": field_def.get("required", False),
                            "is_parent": parent == ref_target,
                        })
                    continue  # Skip naming convention check if explicit ref found

                # Check for naming convention (e.g., orderId -> Order)
                if isinstance(field_type, str) and field_type == "string" and field_name.endswith("Id"):
                    # Infer reference from naming convention
                    inferred_target = field_name[:-2]  # Remove "Id"
                    inferred_target = inferred_target[0].upper() + inferred_target[1:]
                    if inferred_target in self.entities:
                        key = (entity_name, field_name, inferred_target)
                        if key not in seen:
                            seen.add(key)
                            references.append({
                                "source_entity": entity_name,
                                "source_field": field_name,
                                "target_entity": inferred_target,
                                "required": field_def.get("required", False),
                                "is_parent": parent == inferred_target,
                            })

        return references

    def _generate_tests_for_reference(self, ref: dict) -> list[ReferenceTestCase]:
        """Generate test cases for a single reference"""
        cases = []
        source = ref["source_entity"]
        field = ref["source_field"]
        target = ref["target_entity"]
        required = ref["required"]
        is_parent = ref.get("is_parent", False)

        # Pattern 1: Valid reference
        cases.append(ReferenceTestCase(
            id=f"ref_{source}_{field}_valid",
            description=f"{source}.{field}: reference to existing {target} should succeed",
            source_entity=source,
            source_field=field,
            target_entity=target,
            pattern="valid_ref",
            is_required=required,
        ))

        # Pattern 2: Invalid reference
        cases.append(ReferenceTestCase(
            id=f"ref_{source}_{field}_invalid",
            description=f"{source}.{field}: reference to non-existent {target} should fail",
            source_entity=source,
            source_field=field,
            target_entity=target,
            pattern="invalid_ref",
            is_required=required,
        ))

        # Pattern 3: Cascade delete (if this is a parent relationship)
        if is_parent:
            cases.append(ReferenceTestCase(
                id=f"ref_{source}_{field}_cascade_delete",
                description=f"Deleting {target} should handle child {source} records",
                source_entity=source,
                source_field=field,
                target_entity=target,
                pattern="cascade_delete",
                is_required=required,
            ))

        # Pattern 4: Orphan prevention (for required references)
        if required:
            cases.append(ReferenceTestCase(
                id=f"ref_{source}_{field}_orphan_prevention",
                description=f"Cannot create {source} without valid {target}",
                source_entity=source,
                source_field=field,
                target_entity=target,
                pattern="orphan_prevention",
                is_required=True,
            ))

        # Pattern 5: Reference update
        cases.append(ReferenceTestCase(
            id=f"ref_{source}_{field}_update",
            description=f"Updating {source}.{field} should validate new {target} exists",
            source_entity=source,
            source_field=field,
            target_entity=target,
            pattern="ref_update",
            is_required=required,
        ))

        return cases

    def _render_empty_tests(self) -> str:
        """Render placeholder when no references found"""
        return '''/**
 * Auto-generated Reference Integrity Tests from TRIR specification
 *
 * No reference fields found in entities.
 *
 * @generated
 */

describe('Reference Integrity Tests (disabled)', () => {
  test.skip('placeholder', () => {
    // No reference fields found
  });
});
'''

    def _render_tests(self, test_cases: list[ReferenceTestCase]) -> str:
        """Render test cases to executable Jest code"""
        lines = [
            '/**',
            ' * Auto-generated Reference Integrity Tests from TRIR specification',
            ' *',
            ' * These tests verify referential integrity:',
            ' * - References to existing entities succeed',
            ' * - References to non-existent entities fail',
            ' * - Cascade delete behavior is correct',
            ' * - Orphan records cannot be created',
            ' *',
            ' * @generated',
            ' */',
            '',
            'import { v4 as uuidv4 } from "uuid";',
            '',
            '// ========== Test Infrastructure ==========',
            '',
            'interface EntityData {',
            '  id?: string;',
            '  [key: string]: unknown;',
            '}',
            '',
            'class MockRepository {',
            '  private data: Map<string, Map<string, EntityData>> = new Map();',
            '',
            '  create(entityType: string, data: EntityData): string {',
            '    if (!this.data.has(entityType)) {',
            '      this.data.set(entityType, new Map());',
            '    }',
            '    const entityId = data.id || uuidv4();',
            '    this.data.get(entityType)!.set(entityId, { ...data, id: entityId });',
            '    return entityId;',
            '  }',
            '',
            '  delete(entityType: string, entityId: string): boolean {',
            '    const entities = this.data.get(entityType);',
            '    if (entities && entities.has(entityId)) {',
            '      entities.delete(entityId);',
            '      return true;',
            '    }',
            '    return false;',
            '  }',
            '',
            '  exists(entityType: string, entityId: string): boolean {',
            '    return this.data.get(entityType)?.has(entityId) ?? false;',
            '  }',
            '',
            '  countByParent(childType: string, parentType: string, parentId: string): number {',
            '    const children = this.data.get(childType);',
            '    if (!children) return 0;',
            '    const parentField = `${parentType.toLowerCase()}Id`;',
            '    let count = 0;',
            '    children.forEach((entity) => {',
            '      if (entity[parentField] === parentId) count++;',
            '    });',
            '    return count;',
            '  }',
            '}',
            '',
            'class ReferenceTestHelper {',
            '  constructor(private repo: MockRepository) {}',
            '',
            '  createEntity(entityType: string, data: EntityData): string {',
            '    return this.repo.create(entityType, data);',
            '  }',
            '',
            '  deleteEntity(entityType: string, entityId: string): boolean {',
            '    return this.repo.delete(entityType, entityId);',
            '  }',
            '',
            '  entityExists(entityType: string, entityId: string): boolean {',
            '    return this.repo.exists(entityType, entityId);',
            '  }',
            '',
            '  countChildren(parentType: string, parentId: string, childType: string): number {',
            '    return this.repo.countByParent(childType, parentType, parentId);',
            '  }',
            '',
            '  generateNonexistentId(): string {',
            '    return `nonexistent-${uuidv4()}`;',
            '  }',
            '}',
            '',
            'function createRefHelper(): ReferenceTestHelper {',
            '  return new ReferenceTestHelper(new MockRepository());',
            '}',
            '',
        ]

        # Group by source entity
        by_entity: dict[str, list[ReferenceTestCase]] = {}
        for tc in test_cases:
            if tc.source_entity not in by_entity:
                by_entity[tc.source_entity] = []
            by_entity[tc.source_entity].append(tc)

        lines.append('// ========== Tests ==========')
        lines.append('')

        for entity_name, cases in by_entity.items():
            lines.append(f"describe('RefIntegrity: {entity_name}', () => {{")
            lines.append('  let refHelper: ReferenceTestHelper;')
            lines.append('')
            lines.append('  beforeEach(() => {')
            lines.append('    refHelper = createRefHelper();')
            lines.append('  });')
            lines.append('')

            for tc in cases:
                lines.extend(self._render_test_method(tc))
                lines.append('')

            lines.append('});')
            lines.append('')

        return '\n'.join(lines)

    def _render_test_method(self, tc: ReferenceTestCase) -> list[str]:
        """Render a single test method"""
        lines = []

        if tc.pattern == "valid_ref":
            lines.append(f"  test('{tc.description}', () => {{")
            lines.append(f'    // Arrange: Create target entity first')
            lines.append(f'    const targetId = refHelper.createEntity("{tc.target_entity}", {{')
            lines.append(f'      id: "target-1",')
            lines.append(f'      // TODO: Add required fields for {tc.target_entity}')
            lines.append(f'    }});')
            lines.append(f'    ')
            lines.append(f'    // Act: Create source entity with valid reference')
            lines.append(f'    const sourceData = {{')
            lines.append(f'      {tc.source_field}: targetId,')
            lines.append(f'      // TODO: Add other required fields for {tc.source_entity}')
            lines.append(f'    }};')
            lines.append(f'    ')
            lines.append(f'    // Assert: Should succeed')
            lines.append(f'    // TODO: Verify entity was created successfully')
            lines.append(f'    throw new Error("Requires repository implementation");')
            lines.append('  });')

        elif tc.pattern == "invalid_ref":
            lines.append(f"  test('{tc.description}', () => {{")
            lines.append(f'    // Arrange: Generate non-existent ID')
            lines.append(f'    const fakeId = refHelper.generateNonexistentId();')
            lines.append(f'    ')
            lines.append(f'    // Act: Try to create source entity with invalid reference')
            lines.append(f'    const sourceData = {{')
            lines.append(f'      {tc.source_field}: fakeId,')
            lines.append(f'      // TODO: Add other required fields for {tc.source_entity}')
            lines.append(f'    }};')
            lines.append(f'    ')
            lines.append(f'    // Assert: Should fail with reference error')
            lines.append(f'    // TODO: Verify validation error is raised')
            lines.append(f'    throw new Error("Requires repository implementation");')
            lines.append('  });')

        elif tc.pattern == "cascade_delete":
            lines.append(f"  test('{tc.description}', () => {{")
            lines.append(f'    // Arrange: Create parent and children')
            lines.append(f'    const parentId = refHelper.createEntity("{tc.target_entity}", {{ id: "parent-1" }});')
            lines.append(f'    refHelper.createEntity("{tc.source_entity}", {{')
            lines.append(f'      {tc.source_field}: parentId,')
            lines.append(f'    }});')
            lines.append(f'    refHelper.createEntity("{tc.source_entity}", {{')
            lines.append(f'      {tc.source_field}: parentId,')
            lines.append(f'    }});')
            lines.append(f'    ')
            lines.append(f'    // Act: Delete parent')
            lines.append(f'    refHelper.deleteEntity("{tc.target_entity}", parentId);')
            lines.append(f'    ')
            lines.append(f'    // Assert: Children should be handled (deleted or orphaned based on policy)')
            lines.append(f'    // TODO: Verify cascade behavior matches policy')
            lines.append(f'    throw new Error("Requires cascade delete policy implementation");')
            lines.append('  });')

        elif tc.pattern == "orphan_prevention":
            lines.append(f"  test('{tc.description}', () => {{")
            lines.append(f'    // Arrange: No parent entity exists')
            lines.append(f'    const fakeParentId = refHelper.generateNonexistentId();')
            lines.append(f'    ')
            lines.append(f'    // Act: Try to create child without valid parent')
            lines.append(f'    const childData = {{')
            lines.append(f'      {tc.source_field}: fakeParentId,')
            lines.append(f'      // TODO: Add other required fields')
            lines.append(f'    }};')
            lines.append(f'    ')
            lines.append(f'    // Assert: Should reject - cannot create orphan')
            lines.append(f'    // TODO: Verify validation error')
            lines.append(f'    throw new Error("Requires orphan prevention implementation");')
            lines.append('  });')

        elif tc.pattern == "ref_update":
            lines.append(f"  test('{tc.description}', () => {{")
            lines.append(f'    // Arrange: Create original target and source')
            lines.append(f'    const originalTargetId = refHelper.createEntity("{tc.target_entity}", {{ id: "target-1" }});')
            lines.append(f'    refHelper.createEntity("{tc.source_entity}", {{')
            lines.append(f'      {tc.source_field}: originalTargetId,')
            lines.append(f'    }});')
            lines.append(f'    ')
            lines.append(f'    // Act: Try to update reference to non-existent target')
            lines.append(f'    const fakeTargetId = refHelper.generateNonexistentId();')
            lines.append(f'    ')
            lines.append(f'    // Assert: Update should fail')
            lines.append(f'    // TODO: Verify validation error on update')
            lines.append(f'    throw new Error("Requires update validation implementation");')
            lines.append('  });')

        return lines

    def _to_snake(self, name: str) -> str:
        """Convert to snake_case"""
        import re
        s1 = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', name)
        return re.sub('([a-z0-9])([A-Z])', r'\1_\2', s1).lower()
