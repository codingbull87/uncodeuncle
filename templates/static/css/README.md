# CSS split plan

`assemble.py` now supports loading ordered `*.css` files from this directory.

Keep `templates/static/base-styles.css` as the compatibility bundle until the
page-layout rules settle. When the component protocol and print planner are
stable, split the bundle in this order:

1. `00-tokens.css`
2. `10-document.css`
3. `20-components.css`
4. `30-visual-rows.css`
5. `40-print.css`

The final HTML should still inline CSS so the report remains a standalone file.
