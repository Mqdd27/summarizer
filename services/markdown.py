from markdown_it import MarkdownIt
from mdit_py_plugins.attrs import attrs_plugin


def render_markdown(text: str) -> str:
    text = text.strip()
    if text.startswith("<think>"):
        end = text.find("</think>")
        if end != -1:
            text = text[end + len("</think>"):].strip()

    md = MarkdownIt("commonmark", {"html": False, "typographer": True})
    md.enable(["table", "strikethrough"])
    return md.render(text)
