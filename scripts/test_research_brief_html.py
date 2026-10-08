import unittest
from research_brief_html import render
class Tests(unittest.TestCase):
 def test_parentheses_in_original_file_and_url_are_not_truncated(self):
  text='[修订原文](reports/基金合同(2026修订).pdf#page=5)及[网页](https://example.org/a(b(c)).pdf)'
  result=render(text)
  self.assertIn('href="reports/基金合同(2026修订).pdf#page=5"',result)
  self.assertIn('href="https://example.org/a(b(c)).pdf"',result)
 def test_unclosed_parenthesis_does_not_generate_wrong_source_link(self):
  self.assertNotIn('href=',render('[原文](report(修订).pdf'))
 def test_parenthesized_unsafe_link_stays_text_and_safe_link_survives(self):
  result=render('[坏链接](javascript:alert(1)) [原文](https://example.org/a(b).pdf)')
  self.assertNotIn('href="javascript:',result)
  self.assertIn('href="https://example.org/a(b).pdf"',result)
 def test_fenced_example_is_not_a_report_claim_or_navigation(self):
  result=render('# 报告\n```md\n## 示例标题\n**示例结论**\n[伪来源](https://example.org/a)\n|a|b|\n|---|---|\n|1|2|\n<script>\n```\n## 真正判断\n实际正文')
  self.assertIn('<pre class="example"><code>## 示例标题',result)
  self.assertNotIn('<h2>示例标题</h2>',result)
  self.assertNotIn('<strong>示例结论</strong>',result)
  self.assertNotIn('href="https://example.org/a"',result)
  self.assertNotIn('<table>',result)
  self.assertNotIn('<script>',result)
  self.assertIn('<h2>真正判断</h2>',result)
  self.assertEqual(result.count('href="#section-'),1)
 def test_fence_requires_matching_character_length_and_no_trailing_text(self):
  result=render('````\n```\n~~~\n```` not-close\n**still literal**\n````\n正文')
  self.assertIn('```\n~~~\n```` not-close\n**still literal**</code>',result)
  self.assertIn('<p>正文</p>',result)
 def test_unclosed_fence_keeps_remaining_example_literal(self):
  result=render('~~~json\n{"value": "<tag>"}\n## 不是正文')
  self.assertIn('&lt;tag&gt;',result)
  self.assertNotIn('<h2>',result)
 def test_fence_closes_list_before_example(self):
  self.assertIn('</ul><pre class="example">',render('- 资料\n```\n示例\n```'))
 def test_bold_opening_judgment_is_not_muted_metadata(self):
  result=render('# 评价标题\n\n**收益较强，但风险代价也更大。**\n\n资料截至某日。')
  self.assertIn('<p class="conclusion"><strong>收益较强，但风险代价也更大。</strong></p>',result)
 def test_later_bold_paragraph_does_not_become_opening_judgment(self):
  for text in ['# 标题\n资料说明\n**附注**','# 标题\n## 依据\n**附注**','# 标题\n- 来源\n**附注**']:
   with self.subTest(text=text):self.assertNotIn('class="conclusion"',render(text))
 def test_emphasis_escaped_and_link_safe(self):
  result=render('> **核心结论**\n\n**<script>**\n\n[**原文**](https://example.org/a)')
  self.assertIn('<p class="conclusion"><strong>核心结论</strong></p>',result)
  self.assertIn('<strong>&lt;script&gt;</strong>',result)
  self.assertIn('<strong>原文</strong></a>',result)
  self.assertNotIn('<script>',result)
 def test_empty_edge_cells_preserved(self):
  self.assertIn('<tr><td></td><td>2</td><td></td></tr>',render('|a|b|c|\n|---|---|---|\n||2||'))
 def test_escaped_pipe_is_one_cell(self):
  self.assertIn('<td>A|C</td><td>2</td>',render('|a|b|\n|---|---|\n|A\\|C|2|'))
 def test_mismatched_columns_fail(self):
  with self.assertRaisesRegex(ValueError,'列数'):render('|a|b|\n|---|---|\n|1|2|3|')
 def test_mismatched_separator_fail(self):
  with self.assertRaisesRegex(ValueError,'列数'):render('|a|b|\n|---|\n|1|2|')
 def test_table(self):self.assertIn('<thead>',render('|a|b|\n|---|---|\n|1|2|'))
 def test_no_raw_html(self):self.assertNotIn('<script>',render('<script>alert(1)</script>'))
 def test_safe_links(self):self.assertIn('href="https://example.org/a"',render('[来源](https://example.org/a)'))
 def test_unsafe_link_not_executed(self):self.assertNotIn('href="javascript:',render('[x](javascript:alert(1))'))
 def test_relative_links(self):self.assertIn('href="commentary/report.html"',render('[报告](commentary/report.html)'))
 def test_network_relative_rejected(self):self.assertNotIn('href=',render('[报告](//evil.test/a)'))
 def test_windows_scheme_rejected(self):self.assertNotIn('href=',render('[报告](C:/secret)'))
 def test_list_closed(self):self.assertRegex(render('- 缺口\n## 依据'),r'</ul>(?:<span[^>]*></span>)?<h2>')
 def test_thematic_breaks_render_as_rules_and_close_lists(self):
  result=render('- 资料\n\n---\n\n附录\n* * *\n_ _ _')
  self.assertEqual(result.count('<hr>'),3)
  self.assertIn('</ul><hr>',result)
  self.assertNotIn('<p>---</p>',result)
 def test_rule_inside_example_remains_literal_and_table_survives(self):
  result=render('```\n---\n```\n|a|b|\n|---|---|\n|1|2|')
  self.assertIn('<code>---</code>',result)
  self.assertNotIn('<hr>',result)
  self.assertIn('<table>',result)
if __name__=='__main__':unittest.main()
