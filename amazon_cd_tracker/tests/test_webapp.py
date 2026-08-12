from src.webapp import _env_flag, _local_ip


def test_env_flag_defaults_when_unset(monkeypatch):
    monkeypatch.delenv("SOME_FLAG", raising=False)
    assert _env_flag("SOME_FLAG") is False
    assert _env_flag("SOME_FLAG", default=True) is True


def test_env_flag_recognizes_truthy_values(monkeypatch):
    for value in ("1", "true", "True", "yes", "on"):
        monkeypatch.setenv("SOME_FLAG", value)
        assert _env_flag("SOME_FLAG") is True


def test_env_flag_recognizes_falsy_values(monkeypatch):
    for value in ("0", "false", "no", "off", ""):
        monkeypatch.setenv("SOME_FLAG", value)
        assert _env_flag("SOME_FLAG") is False


def test_local_ip_returns_a_string_without_raising():
    # Best-effort: just needs to resolve without network access actually
    # working (UDP connect() only asks the OS to pick a route, no packets).
    ip = _local_ip()
    assert isinstance(ip, str)
    assert ip
