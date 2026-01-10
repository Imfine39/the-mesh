"""Spec file storage, backups, and templates management."""

import json
import re
import shutil
from datetime import datetime
from pathlib import Path


class SpecStorage:
    """Manages spec file storage, backups, and templates"""

    VALID_SECTIONS = [
        "meta", "state", "requirements", "derived", "functions", "scenarios",
        "invariants", "stateMachines", "events", "subscriptions", "roles",
        "sagas", "schedules", "gateways", "deadlines", "externalServices",
        "constraints", "relations", "dataPolicies", "auditPolicies"
    ]

    MINIMAL_TEMPLATE = {
        "meta": {
            "id": "new-spec",
            "title": "New Specification",
            "version": "0.1.0",
            "domain": "general"
        },
        "state": {}
    }

    def __init__(self, base_dir: Path | None = None, max_backups: int = 10):
        self.base_dir = base_dir or Path.home() / ".mesh" / "specs"
        self.backup_dir = self.base_dir / ".backups"
        self.template_dir = self.base_dir / ".templates"
        self.max_backups = max_backups

    def ensure_dirs(self) -> None:
        """Create storage directories if they don't exist"""
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        self.template_dir.mkdir(parents=True, exist_ok=True)

    def sanitize_id(self, spec_id: str) -> str:
        """Sanitize spec ID for filesystem use"""
        sanitized = re.sub(r'[^\w\-_.]', '_', spec_id)
        sanitized = sanitized.strip('._')
        return sanitized or "unnamed"

    def spec_path(self, spec_id: str) -> Path:
        """Get path for a spec file"""
        sanitized = self.sanitize_id(spec_id)
        if not sanitized.endswith('.mesh.json'):
            sanitized = f"{sanitized}.mesh.json"
        return self.base_dir / sanitized

    def create_backup(self, spec_id: str) -> Path | None:
        """Create timestamped backup, prune old backups"""
        spec_file = self.spec_path(spec_id)
        if not spec_file.exists():
            return None

        sanitized_id = self.sanitize_id(spec_id)
        backup_subdir = self.backup_dir / sanitized_id
        backup_subdir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_name = f"{timestamp}_{sanitized_id}.mesh.json"
        backup_path = backup_subdir / backup_name

        shutil.copy2(spec_file, backup_path)
        self._prune_backups(sanitized_id)

        return backup_path

    def _prune_backups(self, spec_id: str) -> None:
        """Remove old backups exceeding max_backups"""
        backup_subdir = self.backup_dir / spec_id
        if not backup_subdir.exists():
            return

        backups = sorted(backup_subdir.glob("*.mesh.json"), reverse=True)
        for old_backup in backups[self.max_backups:]:
            old_backup.unlink()

    def list_specs(self, include_meta: bool = True) -> list[dict]:
        """List all spec files"""
        self.ensure_dirs()
        specs = []

        for spec_file in self.base_dir.glob("*.mesh.json"):
            entry = {
                "filename": spec_file.name,
                "spec_id": spec_file.stem.replace('.trir', ''),
                "modified": datetime.fromtimestamp(spec_file.stat().st_mtime).isoformat(),
                "size": spec_file.stat().st_size
            }

            if include_meta:
                try:
                    with open(spec_file) as f:
                        spec = json.load(f)
                        entry["meta"] = spec.get("meta", {})
                except (json.JSONDecodeError, IOError):
                    entry["meta"] = None
                    entry["error"] = "Failed to read meta"

            specs.append(entry)

        return sorted(specs, key=lambda x: x["modified"], reverse=True)

    def read_spec(self, spec_id: str) -> dict | None:
        """Read a spec file"""
        spec_file = self.spec_path(spec_id)
        if not spec_file.exists():
            return None

        with open(spec_file) as f:
            return json.load(f)

    def write_spec(self, spec: dict, spec_id: str | None = None) -> Path:
        """Write a spec to file"""
        self.ensure_dirs()

        if spec_id is None:
            spec_id = spec.get("meta", {}).get("id", "unnamed")

        spec_file = self.spec_path(spec_id)

        with open(spec_file, 'w') as f:
            json.dump(spec, f, indent=2, ensure_ascii=False)

        return spec_file

    def delete_spec(self, spec_id: str, keep_backup: bool = True) -> bool:
        """Delete a spec file"""
        spec_file = self.spec_path(spec_id)
        if not spec_file.exists():
            return False

        if keep_backup:
            self.create_backup(spec_id)

        spec_file.unlink()
        return True

    def list_backups(self, spec_id: str, limit: int = 10) -> list[dict]:
        """List backup versions of a spec"""
        sanitized_id = self.sanitize_id(spec_id)
        backup_subdir = self.backup_dir / sanitized_id

        if not backup_subdir.exists():
            return []

        backups = []
        for backup_file in sorted(backup_subdir.glob("*.mesh.json"), reverse=True)[:limit]:
            timestamp_str = backup_file.name.split('_')[0] + '_' + backup_file.name.split('_')[1]
            try:
                timestamp = datetime.strptime(timestamp_str, "%Y%m%d_%H%M%S")
            except ValueError:
                timestamp = datetime.fromtimestamp(backup_file.stat().st_mtime)

            backups.append({
                "filename": backup_file.name,
                "timestamp": timestamp.isoformat(),
                "path": str(backup_file),
                "size": backup_file.stat().st_size
            })

        return backups

    def restore_backup(self, spec_id: str, backup_timestamp: str) -> dict | None:
        """Restore a spec from a backup version"""
        sanitized_id = self.sanitize_id(spec_id)
        backup_subdir = self.backup_dir / sanitized_id

        if not backup_subdir.exists():
            return None

        for backup_file in backup_subdir.glob("*.mesh.json"):
            if backup_timestamp in backup_file.name:
                with open(backup_file) as f:
                    return json.load(f)

        return None

    def get_template(self, template_name: str) -> dict | None:
        """Get a built-in template"""
        templates = {
            "minimal": self.MINIMAL_TEMPLATE,
        }
        return templates.get(template_name)
