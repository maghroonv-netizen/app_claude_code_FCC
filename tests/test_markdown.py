from fcc import markdown
from fcc.theme import palette_for


def test_basic_blocks():
    html_text = markdown.to_html("# Title\n\nSome **bold** and _italic_ and `code`.\n\n- one\n- two\n")
    assert "<h2>Title</h2>" in html_text
    assert "<b>bold</b>" in html_text
    assert "<i>italic</i>" in html_text
    assert 'class="md-inline"' in html_text
    assert "<li>one</li>" in html_text


def test_code_block_and_streaming_fence():
    source = "```python\nprint('hi')\n```\n"
    html_text = markdown.to_html(source)
    assert "md-codeblock" in html_text
    assert 'md-codelang">python' in html_text
    assert "print" in html_text and "hi" in html_text
    partial = "```python\nprint('unterminated"
    html_text = markdown.to_html(partial, streaming=True)
    assert "md-codeblock" in html_text


def test_html_is_escaped():
    html_text = markdown.to_html("<script>alert(1)</script>")
    assert "<script>" not in html_text
    assert "&lt;script&gt;" in html_text


def test_links_sanitised():
    good = markdown.to_html("[ok](https://example.com/a_b)")
    assert 'href="https://example.com/a_b"' in good
    bad = markdown.to_html("[evil](javascript:alert(1))")
    assert "javascript:" not in bad


def test_table_and_tasklist():
    source = "| a | b |\n|---|---|\n| 1 | 2 |\n\n- [x] done\n- [ ] todo\n"
    html_text = markdown.to_html(source)
    assert "<table" in html_text
    assert "<th>a</th>" in html_text
    assert 'class="md-task done"' in html_text
    assert 'class="md-task todo"' in html_text


def test_css_contains_palette_colours():
    palette = palette_for("dark")
    css = markdown.markdown_css(palette, 14)
    assert f"font-size: 14px" in css
    assert palette.text in css
    assert "pre.md-code" in css
    light_css = markdown.markdown_css(palette_for("light"), 13)
    assert palette_for("light").text in light_css


def test_plain_text_stripper():
    assert markdown.plain_text("**hi** `x` [link](http://a.b)") == "hi x link"
