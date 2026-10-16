"""Queryable finite scientific contracts; broad roadmap rows are not capabilities.

The JSON subset of YAML avoids introducing a mandatory parser. A contract lists
specific operations/domain restrictions and refuses undeclared operations rather
than treating the existence of a module as evidence of scientific generality.
"""
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from .semantic_contracts import canonical_payload, load_json, require_fields, require_text
from .semantic_ir import fingerprint, rational


@dataclass(frozen=True)
class ScientificCapabilities:
    manifest_json: str

    def __post_init__(self):
        data = load_json(self.manifest_json)
        require_fields(data, {'schema_version', 'owner', 'profiles', 'scope'})
        if type(data['schema_version']) is not int or data['schema_version'] != 1:
            raise ValueError('Unsupported capability schema')
        require_text(data['owner'], 'owner', limit=256)
        require_text(data['scope'], 'scope')
        profiles = data['profiles']
        if not isinstance(profiles, list) or not 1 <= len(profiles) <= 64:
            raise ValueError('One to 64 explicit profiles required')
        identities = set()
        for profile in profiles:
            require_fields(profile, {'id', 'requirements', 'domain', 'operations', 'refused',
                'absolute_tolerance', 'relative_tolerance', 'implementation', 'tests', 'limitations'})
            identifier = require_text(profile['id'], 'profile id', limit=128)
            if identifier in identities:
                raise ValueError('Duplicate scientific profile')
            identities.add(identifier)
            for field in ('domain', 'limitations'):
                require_text(profile[field], field)
            for field in ('operations', 'refused', 'implementation', 'tests'):
                values = profile[field]
                if not isinstance(values, list) or not 1 <= len(values) <= 128:
                    raise ValueError('Bounded explicit capability lists required')
                if any(not isinstance(item, str) or not item.strip() or len(item)>4096 for item in values):
                    raise ValueError('Invalid capability text')
                if len(set(values)) != len(values):
                    raise ValueError('Duplicate capability entry')
            if set(profile['operations']) & set(profile['refused']):
                raise ValueError('Operation simultaneously supported and refused')
            requirements = profile['requirements']
            if (not isinstance(requirements, list) or not requirements or len(requirements)>213
                or any(type(key) is not int or not 1 <= key <= 213 for key in requirements)
                or len(set(requirements)) != len(requirements)):
                raise ValueError('Explicit original roadmap identities required')
            for field in ('absolute_tolerance', 'relative_tolerance'):
                value = profile[field]
                if not isinstance(value, str) or not 0 <= rational(value) <= 1:
                    raise ValueError('Exact nonnegative tolerance in [0,1] required')
            for name in profile['implementation']+profile['tests']:
                path = PurePosixPath(name)
                if (path.is_absolute() or '..' in path.parts or '\\' in name
                    or ':' in name or path.as_posix() != name or name == '.'):
                    raise ValueError('Repository-relative evidence path required')
        object.__setattr__(self,'manifest_json',canonical_payload(data))

    @classmethod
    def load(cls, path):
        with Path(path).open('rb') as stream:
            raw = stream.read(1_000_001)
        if len(raw)>1_000_000:
            raise ValueError('Capability manifest exceeds byte budget')
        return cls(raw.decode('utf-8'))

    @property
    def content_id(self):
        return fingerprint(load_json(self.manifest_json))

    def query(self, profile_id, operation):
        """Return a detached explicit contract; never execute caller code."""
        for profile in load_json(self.manifest_json)['profiles']:
            if profile['id'] == profile_id:
                if operation not in profile['operations']:
                    raise NotImplementedError('Operation outside this declared scientific profile')
                return profile
        raise NotImplementedError('Unknown scientific profile')

    def validate_evidence(self, root):
        root = Path(root).resolve()
        for profile in load_json(self.manifest_json)['profiles']:
            for name in profile['implementation']+profile['tests']:
                path = (root/name).resolve()
                if not path.is_relative_to(root) or not path.is_file():
                    raise ValueError('Missing or escaping capability evidence: '+name)
        return True
