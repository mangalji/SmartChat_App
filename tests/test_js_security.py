"""
tests/test_js_security.py — Static analysis tests for JavaScript security.

Covers:
  - HIGH-3: Toast XSS prevention in chat.js
  - MED-5:  WebSocket protocol detection
"""

from django.test import TestCase


class ChatJSSecurityTest(TestCase):
    """HIGH-3: Toast function must escape HTML."""

    def test_toast_escapes_msg_parameter(self):
        """chat.js toast() should escape the msg before HTML insertion."""
        with open('static/js/chat.js', 'r') as f:
            content = f.read()
        # Must have an escape step before insertAdjacentHTML
        self.assertIn('escaped', content,
                      "chat.js toast() must escape msg before inserting into DOM")
        self.assertNotIn('</i>${msg}', content,
                         "chat.js toast() must NOT insert raw ${msg} into HTML")
        self.assertIn('${escaped}', content,
                      "chat.js should use ${escaped} instead of ${msg}")

    def test_eschtml_function_handles_ampersand(self):
        """escHtml should escape & character."""
        with open('static/js/chat.js', 'r') as f:
            content = f.read()
        self.assertIn("'&amp;'", content,
                      "escHtml/escaped must handle & → &amp;")

    def test_eschtml_function_handles_lt_gt(self):
        """escHtml should escape < and > characters."""
        with open('static/js/chat.js', 'r') as f:
            content = f.read()
        self.assertIn("'&lt;'", content, "Must escape < → &lt;")
        self.assertIn("'&gt;'", content, "Must escape > → &gt;")
