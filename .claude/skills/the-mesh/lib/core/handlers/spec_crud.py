"""Spec CRUD handlers for The Mesh."""

import copy
from pathlib import Path
from typing import Any

from core.validator import MeshValidator
from core.storage import SpecStorage
from core.handlers.generation import compute_spec_changes, sync_after_change
from config.project import ProjectConfig


def spec_list(validator: MeshValidator, storage: SpecStorage, args: dict) -> dict:
    """List all spec files in storage"""
    include_meta = args.get("include_meta", True)
    specs = storage.list_specs(include_meta)
    return {
        "specs": specs,
        "count": len(specs),
        "storage_path": str(storage.base_dir),
    }


def spec_read(validator: MeshValidator, storage: SpecStorage, args: dict) -> dict:
    """Read a spec file from storage"""
    spec_id = args["spec_id"]
    sections = args.get("sections")

    spec = storage.read_spec(spec_id)
    if spec is None:
        return {
            "found": False,
            "error": f"Spec not found: {spec_id}",
            "available_specs": [s["spec_id"] for s in storage.list_specs(False)]
        }

    if sections:
        filtered = {"meta": spec.get("meta", {})}
        for section in sections:
            if section in spec:
                filtered[section] = spec[section]
        spec = filtered

    return {
        "found": True,
        "spec": spec,
        "path": str(storage.spec_path(spec_id)),
    }


def spec_write(validator: MeshValidator, storage: SpecStorage, args: dict) -> dict:
    """Write/create a spec file with automatic bundle sync"""
    spec = args["spec"]
    spec_id = args.get("spec_id") or spec.get("meta", {}).get("id")
    validate = args.get("validate", True)
    force = args.get("force", False)
    no_sync = args.get("no_sync", False)

    if not spec_id:
        return {"success": False, "error": "No spec_id provided and meta.id missing"}

    # Read previous spec for diff calculation (before backup)
    previous_spec = storage.read_spec(spec_id)

    # Validate if requested
    validation_result = None
    if validate:
        result = validator.validate(spec)
        validation_result = {
            "valid": result.valid,
            "error_count": len(result.errors),
            "warning_count": len(result.warnings),
        }
        if not result.valid and not force:
            return {
                "success": False,
                "error": "Validation failed",
                "validation": validation_result,
                "errors": [e.to_structured().to_dict() for e in result.errors[:10]]
            }

    # Create backup if file exists
    backup_created = False
    if storage.spec_path(spec_id).exists():
        storage.create_backup(spec_id)
        backup_created = True

    # Write spec
    path = storage.write_spec(spec, spec_id)

    result = {
        "success": True,
        "path": str(path),
        "spec_id": spec_id,
        "validation": validation_result,
        "backup_created": backup_created,
    }

    # Auto-sync bundles if not disabled
    if not no_sync:
        changes = compute_spec_changes(previous_spec, spec)
        if changes:
            # Determine output directory from project config
            spec_path = Path(path)
            base_dir = spec_path.parent
            project_config = ProjectConfig(base_dir)
            config = project_config.load()
            language = config.get("language", "python")

            sync_result = sync_after_change(validator, storage, {
                "spec": spec,
                "changes": changes,
                "language": language,
                "output_dir": str(base_dir),
            })
            result["sync"] = {
                "performed": True,
                "changes_count": len(changes),
                "updated_functions": sync_result.get("updated_functions", []),
                "updated_tests": sync_result.get("updated_tests", []),
            }
        else:
            result["sync"] = {"performed": False, "reason": "no_changes"}

    return result


def spec_delete(validator: MeshValidator, storage: SpecStorage, args: dict) -> dict:
    """Delete a spec file"""
    spec_id = args["spec_id"]
    keep_backup = args.get("keep_backup", True)

    if not storage.spec_path(spec_id).exists():
        return {
            "success": False,
            "error": f"Spec not found: {spec_id}",
        }

    deleted = storage.delete_spec(spec_id, keep_backup)
    return {
        "success": deleted,
        "deleted": spec_id,
        "backup_kept": keep_backup,
    }


def spec_get_section(validator: MeshValidator, storage: SpecStorage, args: dict) -> dict:
    """Get a specific section from a spec"""
    spec_id = args["spec_id"]
    section = args["section"]
    key = args.get("key")

    spec = storage.read_spec(spec_id)
    if spec is None:
        return {"found": False, "error": f"Spec not found: {spec_id}"}

    if section not in spec:
        return {
            "found": False,
            "error": f"Section not found: {section}",
            "available_sections": list(spec.keys()),
            "valid_sections": SpecStorage.VALID_SECTIONS,
        }

    data = spec[section]
    if key:
        if isinstance(data, dict) and key in data:
            data = data[key]
        else:
            return {
                "found": False,
                "error": f"Key not found: {key}",
                "available_keys": list(data.keys()) if isinstance(data, dict) else [],
            }

    return {
        "found": True,
        "section": section,
        "key": key,
        "data": data,
    }


def spec_update_section(validator: MeshValidator, storage: SpecStorage, args: dict) -> dict:
    """Update a specific section or item within a spec"""
    spec_id = args["spec_id"]
    section = args["section"]
    key = args.get("key")
    data = args["data"]
    merge = args.get("merge", False)
    validate = args.get("validate", True)

    spec = storage.read_spec(spec_id)
    if spec is None:
        return {"success": False, "error": f"Spec not found: {spec_id}"}

    # Update section
    if section not in spec:
        spec[section] = {} if key else data

    if key:
        if not isinstance(spec[section], dict):
            return {"success": False, "error": f"Section {section} is not a dict, cannot use key"}
        if merge and key in spec[section] and isinstance(spec[section][key], dict):
            spec[section][key] = {**spec[section][key], **data}
        else:
            spec[section][key] = data
    else:
        if merge and isinstance(spec[section], dict) and isinstance(data, dict):
            spec[section] = {**spec[section], **data}
        else:
            spec[section] = data

    # Validate and save
    return spec_write(validator, storage, {
        "spec": spec,
        "spec_id": spec_id,
        "validate": validate,
        "force": False
    })


def spec_delete_section(validator: MeshValidator, storage: SpecStorage, args: dict) -> dict:
    """Delete a section or item from a spec"""
    spec_id = args["spec_id"]
    section = args["section"]
    key = args.get("key")

    spec = storage.read_spec(spec_id)
    if spec is None:
        return {"success": False, "error": f"Spec not found: {spec_id}"}

    if section not in spec:
        return {"success": False, "error": f"Section not found: {section}"}

    deleted_key = None
    if key:
        if isinstance(spec[section], dict) and key in spec[section]:
            del spec[section][key]
            deleted_key = key
        else:
            return {"success": False, "error": f"Key not found: {key}"}
    else:
        if section in ["meta", "state"]:
            return {"success": False, "error": f"Cannot delete required section: {section}"}
        del spec[section]

    # Save without validation (deletion might make spec invalid temporarily)
    storage.create_backup(spec_id)
    storage.write_spec(spec, spec_id)

    return {
        "success": True,
        "deleted_section": section if not key else None,
        "deleted_key": deleted_key,
    }


def spec_create_from_template(validator: MeshValidator, storage: SpecStorage, args: dict) -> dict:
    """Create a new spec from a template"""
    template_name = args["template"]
    meta = args["meta"]

    template = storage.get_template(template_name)
    if template is None:
        return {
            "success": False,
            "error": f"Unknown template: {template_name}",
            "available_templates": ["minimal"],
        }

    # Deep copy and update meta
    spec = copy.deepcopy(template)
    spec["meta"] = {**spec.get("meta", {}), **meta}

    spec_id = meta.get("id")
    if storage.spec_path(spec_id).exists():
        return {
            "success": False,
            "error": f"Spec already exists: {spec_id}",
        }

    path = storage.write_spec(spec, spec_id)
    return {
        "success": True,
        "spec": spec,
        "path": str(path),
        "template_used": template_name,
    }


def spec_list_backups(validator: MeshValidator, storage: SpecStorage, args: dict) -> dict:
    """List backup versions of a spec"""
    spec_id = args["spec_id"]
    limit = args.get("limit", 10)

    backups = storage.list_backups(spec_id, limit)
    return {
        "spec_id": spec_id,
        "backups": backups,
        "count": len(backups),
    }


def spec_restore_backup(validator: MeshValidator, storage: SpecStorage, args: dict) -> dict:
    """Restore a spec from a backup version"""
    spec_id = args["spec_id"]
    backup_timestamp = args["backup_timestamp"]
    backup_current = args.get("backup_current", True)

    # Find and load backup
    backup_spec = storage.restore_backup(spec_id, backup_timestamp)
    if backup_spec is None:
        backups = storage.list_backups(spec_id)
        return {
            "success": False,
            "error": f"Backup not found for timestamp: {backup_timestamp}",
            "available_backups": [b["timestamp"] for b in backups],
        }

    # Backup current version if requested
    current_backed_up = False
    if backup_current and storage.spec_path(spec_id).exists():
        storage.create_backup(spec_id)
        current_backed_up = True

    # Write restored spec
    path = storage.write_spec(backup_spec, spec_id)

    return {
        "success": True,
        "restored_from": backup_timestamp,
        "current_backed_up": current_backed_up,
        "path": str(path),
    }


# Handler registry
HANDLERS = {
    "spec_list": spec_list,
    "spec_read": spec_read,
    "spec_write": spec_write,
    "spec_delete": spec_delete,
    "spec_get_section": spec_get_section,
    "spec_update_section": spec_update_section,
    "spec_delete_section": spec_delete_section,
    "spec_create_from_template": spec_create_from_template,
    "spec_list_backups": spec_list_backups,
    "spec_restore_backup": spec_restore_backup,
}
