"""Recognize standalone list decorations without changing the source text."""

LAYOUT_BULLETS = frozenset('•◦▪▫●○■□◆◇♦◊‣⁃∙\uf075\uf0b7\uf0a7\uf0d8')


def is_layout_symbol(text):
    chars = ''.join(str(text).split())
    return bool(chars) and all(c in LAYOUT_BULLETS for c in chars)


def presentation_reviews(resume, reviews):
    """Keep provenance/coverage intact; omit decorations from display and pins."""
    layout = {u['id'] for u in resume['units'] if is_layout_symbol(u['text'])}
    visible = []
    for review in reviews:
        content = [uid for uid in review['unit_ids'] if uid not in layout]
        if content:
            visible.append(dict(review, unit_ids=content))
    return visible, sorted(layout)
