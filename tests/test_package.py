import json
import re
import unittest
from pathlib import Path

R = Path(__file__).resolve().parents[1]


class PackageTests(unittest.TestCase):
    def test_links(self):
        for p in R.rglob('*.md'):
            for dest in re.findall(r'\]\(([^)]+)\)', p.read_text()):
                if '://' in dest or dest.startswith('#'):
                    continue
                with self.subTest(file=str(p), link=dest):
                    self.assertTrue((p.parent / dest.split('#')[0]).exists())

    def test_frontmatter(self):
        text = (R / 'SKILL.md').read_text()
        m = re.match(r'---\nname: (.+)\ndescription: (.+)\n---\n', text)
        self.assertIsNotNone(m)
        self.assertEqual(m.group(1), R.name)

    def test_upstream_fingerprints(self):
        rows = json.loads((R / 'references/upstream-sources.json').read_text())
        self.assertEqual(len(rows), 2)
        for r in rows:
            self.assertRegex(r['blob_sha'], r'^[0-9a-f]{40}$')

    def test_portable_paths(self):
        for p in list((R / 'references').glob('*.md')) + [R / 'SKILL.md']:
            self.assertNotIn('/Users/', p.read_text())

    def test_market_snapshot_has_no_data_rows(self):
        rows = [l for l in (R / 'references/market-snapshot.md').read_text().splitlines()
                if l.startswith('|')]
        self.assertEqual(len(rows), 2, '模板只应有表头和分隔行，价格等易变数据不入库')


    def test_cheatsheet_dated_and_without_model_names(self):
        text = (R / 'references/cheatsheet.md').read_text()
        self.assertRegex(text, r'判断基于 20\d\d 年')
        self.assertIn('以最新官方文档为准', text)
        for rows in (text.split('## 一')[1].split('## 二')[0],):
            self.assertGreaterEqual(len([l for l in rows.splitlines() if l.startswith('|')]), 8)

    def test_model_evidence_index_has_no_data_rows(self):
        rows = [l for l in (R / 'references/model-evidence/index.md').read_text().splitlines()
                if l.startswith('|')]
        self.assertEqual(len(rows), 2, '索引在没有经 CONTRIBUTING 审核的记录前保持为空')

    def test_contributing_requires_core_fields(self):
        text = (R / 'CONTRIBUTING.md').read_text()
        for key in ('可复现', '样本量', '版本', '利益关系', '客户数据'):
            self.assertIn(key, text)


if __name__ == '__main__':
    unittest.main()
