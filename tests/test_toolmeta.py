from fcc.claude import toolmeta


def test_subjects_and_titles():
    assert toolmeta.subject_for("Bash", {"command": "git status"}) == "git status"
    assert toolmeta.subject_for("Read", {"file_path": "/a/b/c.py"}) == "/a/b/c.py"
    assert toolmeta.title_for("Bash", {"command": "ls -la", "description": "List files"}) == "List files"
    assert toolmeta.title_for("Edit", {"file_path": "/x/src/app.py"}).endswith("src/app.py")
    assert toolmeta.title_for("WebSearch", {"query": "qt"}).startswith("Web search")


def test_bash_rule_pattern():
    from fcc.claude.permissions import bash_rule_pattern

    assert bash_rule_pattern("git status --short") == "git status*"
    assert bash_rule_pattern("ls") == "ls"
    assert bash_rule_pattern("npm install --save") == "npm install*"


def test_diff_from_structured():
    patch = [{"oldStart": 6, "oldLines": 2, "newStart": 6, "newLines": 2,
              "lines": [" context", "-old line", "+new line"]}]
    diff = toolmeta.diff_from_structured(patch)
    assert diff[0].kind == "hunk"
    assert diff[1].kind == "ctx"
    assert diff[2].kind == "del" and diff[2].text == "old line"
    assert diff[3].kind == "add" and diff[3].new_no == 7


def test_describe_output_edit_diff():
    detail = toolmeta.describe_output(
        "Edit", {"file_path": "/x/y.py"},
        [{"type": "text", "text": "updated"}],
        {"filePath": "/x/y.py",
         "structuredPatch": [{"oldStart": 1, "oldLines": 1, "newStart": 1, "newLines": 1,
                              "lines": ["-a", "+b"]}],
         "gitDiff": {"filename": "y.py", "status": "modified", "additions": 1, "deletions": 1}})
    assert detail.kind == "diff"
    assert detail.stats["add"] == 1 and detail.stats["del"] == 1
    assert any(key == "Git" for key, _ in detail.rows)


def test_describe_output_bash():
    detail = toolmeta.describe_output("Bash", {"command": "ls"}, "ignored",
                                      {"stdout": "hello", "stderr": "warn"})
    assert detail.body == "hello"
    assert any(key == "stderr" for key, _ in detail.rows)


def test_describe_output_glob_and_todos():
    glob = toolmeta.describe_output("Glob", {}, "", {"filenames": ["a.py", "b.py"], "numFiles": 2})
    assert glob.kind == "files" and len(glob.items) == 2
    todos = toolmeta.describe_output("TodoWrite", {"todos": [{"content": "x", "status": "pending", "activeForm": "x"}]},
                                     "", {"newTodos": [{"content": "x", "status": "completed", "activeForm": "x"}]})
    assert todos.kind == "todos" and todos.items[0]["status"] == "completed"


def test_language_detection():
    assert toolmeta.language_for_path("a/main.py") == "python"
    assert toolmeta.language_for_path("a/b.tsx") == "tsx"
    assert toolmeta.language_for_path("README.md") == "markdown"
