from __future__ import annotations

from .models import Article, BlockKind, ContentBlock


def article_to_markdown(article: Article) -> str:
    lines = [f"# {article.title}", ""]
    if article.author:
        lines.append(f"**Author:** {article.author}")
    if article.source_url:
        label = article.site or article.source_url
        lines.append(f"**Source:** [{label}]({article.source_url})")
    lines.append("")
    for block in article.blocks:
        if block.kind == BlockKind.HEADING:
            lines.extend([f"{'#' * max(2, block.level)} {block.text}", ""])
        elif block.kind == BlockKind.LIST_ITEM:
            lines.append(f"- {block.text}")
        elif block.kind == BlockKind.QUOTE:
            lines.extend([f"> {block.text}", ""])
        elif block.kind == BlockKind.CODE:
            lines.extend(["```", block.text, "```", ""])
        else:
            lines.extend([block.text, ""])
    return "\n".join(lines).rstrip() + "\n"
