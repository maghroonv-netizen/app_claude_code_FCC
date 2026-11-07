from fcc.config import AppConfig, PermissionRule


def test_project_and_trust(tmp_config):
    record = tmp_config.upsert_project("/tmp/demo project")
    assert record.name == "demo project"
    assert not tmp_config.is_trusted(record.path)
    tmp_config.set_trusted(record.path, True)
    assert tmp_config.is_trusted("/tmp/demo project/")
    assert tmp_config.project("/tmp/demo project").trusted


def test_session_lifecycle(tmp_config):
    tmp_config.upsert_project("/tmp/proj")
    session = tmp_config.create_session("/tmp/proj", "First chat")
    assert tmp_config.sessions_for("/tmp/proj")[0].id == session.id
    tmp_config.rename_session(session.id, "Renamed")
    assert tmp_config.session(session.id).title == "Renamed"
    tmp_config.delete_session(session.id)
    assert tmp_config.session(session.id) is None
    assert tmp_config.sessions_for("/tmp/proj") == []


def test_rules_priority_deny_first(tmp_config):
    allow = PermissionRule(tool="Bash", pattern="git *", behavior="allow", scope="global")
    deny = PermissionRule(tool="Bash", pattern="git push *", behavior="deny", scope="global")
    tmp_config.add_rule(allow)
    tmp_config.add_rule(deny)
    found = tmp_config.find_rule("Bash", "git push origin main")
    assert found is not None and found.behavior == "deny"
    found = tmp_config.find_rule("Bash", "git status")
    assert found is not None and found.behavior == "allow"
    assert tmp_config.find_rule("Bash", "rm -rf /") is None


def test_rule_scopes(tmp_config):
    tmp_config.upsert_project("/tmp/a")
    tmp_config.upsert_project("/tmp/b")
    tmp_config.add_rule(PermissionRule(tool="Write", pattern="*", behavior="allow",
                                       scope="project", project="/tmp/a"))
    assert tmp_config.find_rule("Write", "/tmp/a/x.py", "/tmp/a") is not None
    assert tmp_config.find_rule("Write", "/tmp/b/x.py", "/tmp/b") is None


def test_save_and_reload(tmp_config, tmp_path):
    from fcc import config as config_module

    tmp_config.upsert_project("/tmp/persist")
    tmp_config.theme = "dark"
    target = tmp_path / "config.json"
    assert config_module.save(tmp_config, target)
    reloaded = config_module.load(target)
    assert reloaded.theme == "dark"
    assert reloaded.project("/tmp/persist") is not None


def test_corrupt_config_recovers(tmp_path):
    from fcc import config as config_module

    target = tmp_path / "config.json"
    target.write_text("{not json", encoding="utf-8")
    config = config_module.load(target)
    assert isinstance(config, AppConfig)
    assert config.theme in ("light", "dark", "system")
