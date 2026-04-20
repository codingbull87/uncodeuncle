import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class PromptReferenceConsistencyTests(unittest.TestCase):
    def test_generator_task_does_not_teach_forbidden_js_color_patterns(self) -> None:
        text = (ROOT / 'templates' / 'prompts' / 'generator-task.md').read_text(encoding='utf-8')
        forbidden_snippets = [
            "color: ['var(--color-primary)'",
            "trim() || '#1e3a5f'",
            "itemStyle: { color: '#0f766e', borderRadius: [6, 6, 0, 0] }",
            "color: [primary, '#64748b', '#166534', '#d97706', '#991b1b']",
        ]
        for snippet in forbidden_snippets:
            self.assertNotIn(snippet, text)

        required_snippets = [
            "getComputedStyle(document.documentElement)",
            "barBorderRadius: [6, 6, 0, 0]",
            "不要写 `|| '#888'` 之类的 fallback",
            "禁止使用 `:host`",
        ]
        for snippet in required_snippets:
            self.assertIn(snippet, text)

    def test_validator_uses_current_bar_radius_contract_term(self) -> None:
        text = (ROOT / 'templates' / 'prompts' / 'validator-task.md').read_text(encoding='utf-8')
        self.assertIn('barBorderRadius', text)
        self.assertNotIn('圆角 `borderRadius`', text)

    def test_echarts_reference_matches_lint_safe_examples(self) -> None:
        text = (ROOT / 'references' / 'echarts-config.md').read_text(encoding='utf-8')
        forbidden_snippets = [
            "color: ['#",
            "itemStyle: { color: '#",
            "lineStyle: { width: 2, color: '#",
            "return params.value >= 0 ? '#",
            "trim() || '#1e3a5f'",
        ]
        for snippet in forbidden_snippets:
            self.assertNotIn(snippet, text)

        required_snippets = [
            "在脚本中直接写 hex 色值",
            "var c = {",
            "barBorderRadius: [6, 6, 0, 0]",
            "不要使用 `:host`",
        ]
        for snippet in required_snippets:
            self.assertIn(snippet, text)


if __name__ == '__main__':
    unittest.main()
