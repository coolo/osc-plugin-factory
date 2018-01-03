from osclib.comments import CommentAPI
import re
import unittest


class TestComment(unittest.TestCase):
    COMMENT = 'short comment'
    COMMENT_INFO = {'foo': 'bar', 'distro': 'openSUSE'}

    def setUp(self):
        self.api = CommentAPI('bogus')
        self.bot = type(self).__name__
        self.comments = {
            1: {'comment': '<!-- {} -->\n\nshort comment'.format(self.bot)},
            2: {'comment': '<!-- {} foo=bar distro=openSUSE -->\n\nshort comment'.format(self.bot)}
        }

    def test_truncate(self):
        comment = "string of text"
        for i in xrange(len(comment) + 1):
            truncated = self.api.truncate(comment, length=i)
            print(truncated)
            self.assertEqual(len(truncated), i)

    def test_truncate_pre(self):
        comment = """
Some text.

<pre>
bar
mar
car
</pre>

## section 2

<pre>
more
lines
than
you
can
handle
</pre>
""".strip()

        for i in xrange(len(comment) + len('...\n</pre>')):
            truncated = self.api.truncate(comment, length=i)
            print('=' * 80)
            print(truncated)
            self.assertTrue(len(truncated) <= i, '{} <= {}'.format(len(truncated), i))
            self.assertEqual(truncated.count('<pre>'), truncated.count('</pre>'))
            self.assertFalse(len(re.findall(r'</?\w+[^\w>]', truncated)))
            tag_count = truncated.count('<pre>') + truncated.count('</pre>')
            self.assertEqual(tag_count, truncated.count('<'))
            self.assertEqual(tag_count, truncated.count('>'))

    def test_add_marker(self):
        comment_marked = self.api.add_marker(self.COMMENT, self.bot)
        self.assertEqual(comment_marked, self.comments[1]['comment'])

        comment_marked = self.api.add_marker(self.COMMENT, self.bot, self.COMMENT_INFO)
        self.assertEqual(comment_marked, self.comments[2]['comment'])
