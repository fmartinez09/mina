from __future__ import annotations

import unittest

from mina_assistant.app.web_search import DuckDuckGoHTMLParser, _duckduckgo_vqd


class DuckDuckGoHTMLParserTest(unittest.TestCase):
    def test_parser_extracts_results_and_decodes_duckduckgo_redirect(self) -> None:
        html = """
        <div class="result">
          <a class="result__a" href="/l/?kh=-1&uddg=https%3A%2F%2Fexample.com%2Fboots">Best boots</a>
          <a class="result__snippet">A useful guide for black ankle boots.</a>
        </div>
        <div class="result">
          <a class="result__a" href="https://example.org/jeans">Wide jeans</a>
          <a class="result__snippet">Ideas for wide leg jeans.</a>
        </div>
        """
        parser = DuckDuckGoHTMLParser(limit=5)
        parser.feed(html)

        self.assertEqual(len(parser.results), 2)
        self.assertEqual(parser.results[0].title, "Best boots")
        self.assertEqual(parser.results[0].url, "https://example.com/boots")
        self.assertEqual(parser.results[0].snippet, "A useful guide for black ankle boots.")
        self.assertEqual(parser.results[1].url, "https://example.org/jeans")

    def test_duckduckgo_vqd_token_patterns(self) -> None:
        self.assertEqual(_duckduckgo_vqd('DDG.pageLayout.load("x"); vqd="4-12345";'), "4-12345")
        self.assertEqual(_duckduckgo_vqd("some-url?vqd=3-67890&iar=images"), "3-67890")


if __name__ == "__main__":
    unittest.main()
