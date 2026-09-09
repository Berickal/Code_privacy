
from exposure_gap.corpus import FreezeManager
from exposure_gap.prompts import PromptMaterializer, PromptRegistry, TargetFieldExtractor


def test_materialize_and_load(tmp_path):
    n = PromptMaterializer().write_all(tmp_path / "prompts")
    assert n == 30
    reg = PromptRegistry(tmp_path / "prompts")
    assert len(reg.templates) == 30
    assert reg.version_hash == PromptRegistry(tmp_path / "prompts").version_hash


def test_render_and_leakage_audit(tmp_path):
    PromptMaterializer().write_all(tmp_path / "prompts")
    reg = PromptRegistry(tmp_path / "prompts")
    src = 'def scale(v, f):\n    """Scale v by f."""\n    return v * f\n'
    fields = TargetFieldExtractor().extract("secret_file_id", src, "python", "web_backend", "src/s.py")
    rendered = reg.render("reproduction", "P1a", fields)
    assert "def scale(v, f)" in rendered
    assert "secret_file_id" not in rendered
    assert reg.audit_no_target_leakage(["secret_file_id"]) == []


def test_freeze_detects_modification(tmp_path):
    (tmp_path / "configs").mkdir()
    (tmp_path / "configs" / "corpus.yaml").write_text("seed: 0\n")
    fm = FreezeManager(tmp_path)
    fm.write()
    assert fm.verify() == []
    (tmp_path / "configs" / "corpus.yaml").write_text("seed: 1\n")
    violations = fm.verify()
    assert any(v.kind == "modified" for v in violations)
