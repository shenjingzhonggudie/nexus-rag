"""归档输入的实际字节必须与冻结提交一致。"""

import importlib.util
from pathlib import Path

import pytest


@pytest.mark.parametrize("tampered", [False, True])
def test_archive_payload_checks_actual_bytes(tmp_path, monkeypatch, tampered):
    path = Path(__file__).resolve().parents[1] / "scripts/rescore_holdout.py"
    spec = importlib.util.spec_from_file_location("rescore_script_under_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, "ROOT", tmp_path)
    frozen = b"original archived configuration\r\n"
    file = tmp_path / "config.yaml"
    file.write_bytes(b"modified\n" if tampered else frozen)
    calls = []
    def fake_git(*args):
        calls.append(args)
        return frozen
    monkeypatch.setattr(module, "git", fake_git)
    if tampered:
        with pytest.raises(ValueError, match="differs from frozen bytes"):
            module.archive_payload(file)
    else:
        assert module.archive_payload(file) == frozen
    assert calls == [("show", f"{module.FREEZE_COMMIT}:config.yaml")]
