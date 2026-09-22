"""Static checks over the template tree.

These catch mistakes that render as visible junk on the page but never raise -
so no functional test would notice them.
"""

import re
from pathlib import Path

from django.conf import settings
from django.test import TestCase

TEMPLATE_ROOT = Path(settings.BASE_DIR) / "templates"

# An opening {# with no #} anywhere on the same line.
UNCLOSED_SHORT_COMMENT = re.compile(r"\{#(?![^\n]*#\})")

# A whole <img ...> tag, which may span several lines.
IMG_TAG = re.compile(r"<img\b[^>]*>", re.S)
ALT_ATTRIBUTE = re.compile(r"\balt\s*=")
EMPTY_ALT = re.compile(r"""\balt\s*=\s*(""|'')""")


def template_files():
    return sorted(TEMPLATE_ROOT.rglob("*.html"))


class TemplateHygieneTests(TestCase):
    def test_templates_exist(self):
        self.assertGreater(len(template_files()), 20)

    def test_no_multiline_short_comments(self):
        """`{# ... #}` is single-line only.

        Django's lexer will not treat it as a comment if the closing `#}` is on
        a later line, so the text renders straight into the page. This has bitten
        this project twice - once printing a note into the toolbar, once
        breaking the avatar menu layout. Use {% comment %} for anything that
        spans lines.
        """
        offenders = []
        for path in template_files():
            for number, line in enumerate(
                path.read_text(encoding="utf-8").splitlines(), start=1
            ):
                if UNCLOSED_SHORT_COMMENT.search(line):
                    offenders.append(
                        f"{path.relative_to(TEMPLATE_ROOT)}:{number}: {line.strip()[:70]}"
                    )

        self.assertEqual(
            offenders,
            [],
            "Multi-line {# #} comment(s) found - these render as visible text. "
            "Use {% comment %}...{% endcomment %} instead:\n  "
            + "\n  ".join(offenders),
        )

    def test_no_unbalanced_comment_tags(self):
        for path in template_files():
            body = path.read_text(encoding="utf-8")
            with self.subTest(template=str(path.relative_to(TEMPLATE_ROOT))):
                self.assertEqual(
                    body.count("{% comment %}"),
                    body.count("{% endcomment %}"),
                    "unbalanced {% comment %} / {% endcomment %}",
                )

    def test_every_img_has_a_non_empty_alt(self):
        """Every <img> must carry a non-empty `alt`.

        A missing `alt` makes screen readers announce the file name. An empty
        `alt=""` is valid HTML for a decorative image, but the SEO crawler the
        site is audited with reports it as "missing alt attribute" - so every
        image gets a real description, even the card thumbnails whose name is
        repeated beside them.
        """
        for path in template_files():
            body = path.read_text(encoding="utf-8")
            for match in IMG_TAG.finditer(body):
                tag = match.group(0)
                line = body.count("\n", 0, match.start()) + 1
                with self.subTest(
                    template=str(path.relative_to(TEMPLATE_ROOT)), line=line
                ):
                    self.assertRegex(tag, ALT_ATTRIBUTE, "<img> without an alt attribute")
                    self.assertNotRegex(tag, EMPTY_ALT, '<img> with an empty alt=""')
