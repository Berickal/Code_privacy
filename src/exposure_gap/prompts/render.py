"""Per-target field extraction for prompt rendering (report Section 7).

No template may name a specific exposed file; every field here is derived mechanically
from the target's own source.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class TargetFields:
    file_id: str
    language: str
    domain: str
    file_path: str
    signature: str
    docstring: str
    imports: str
    project_name: str
    body_reference: str  # gold implementation, used only for scoring (never in prompts)

    def render_context(self) -> dict:
        d = asdict(self)
        d.pop("body_reference")
        return d


class TargetFieldExtractor:
    _PY_SIG = re.compile(r"^(?:async\s+)?(def\s+\w+\s*\([^)]*\)\s*(?:->\s*[^:]+)?):", re.M)
    _PY_DOC = re.compile(r'"""(.*?)"""', re.S)
    _PY_IMPORT = re.compile(r"^(?:import|from)\s+.+$", re.M)
    _PROJECT = re.compile(r"(?:project|package|module)\s*[:=]\s*([\w\-./]+)", re.I)

    def extract(
        self, file_id: str, source: str, language: str, domain: str, file_path: str
    ) -> TargetFields:
        sig_m = self._PY_SIG.search(source)
        signature = sig_m.group(1).strip() if sig_m else ""
        doc_m = self._PY_DOC.search(source)
        docstring = doc_m.group(1).strip() if doc_m else ""
        imports = "\n".join(self._PY_IMPORT.findall(source)[:20])
        proj_m = self._PROJECT.search(source[:400])
        project = proj_m.group(1) if proj_m else ""
        body = self._body_after_signature(source, sig_m.end() if sig_m else 0)
        return TargetFields(
            file_id=file_id,
            language=language,
            domain=domain,
            file_path=file_path,
            signature=signature,
            docstring=docstring,
            imports=imports,
            project_name=project,
            body_reference=body,
        )

    @staticmethod
    def _body_after_signature(source: str, start: int) -> str:
        tail = source[start:]
        # strip a leading docstring from the body reference
        tail = re.sub(r'^\s*""".*?"""\s*', "", tail, count=1, flags=re.S)
        return tail.strip("\n")
