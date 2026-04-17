# CSS split plan

`assemble.py` loads ordered `*.css` files from this directory first.

`templates/static/base-styles.css` is now a compatibility snapshot.
Split CSS files are the source of truth. Rebuild the snapshot with:

`python3 scripts/build_base_styles.py`

Keep the split order stable:

1. `00-tokens.css`
2. `10-document.css`
3. `20-components.css`
4. `30-visual-rows.css`
5. `40-print.css`

The final HTML should still inline CSS so the report remains a standalone file.
