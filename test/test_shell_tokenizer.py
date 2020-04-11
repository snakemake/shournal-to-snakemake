import unittest

from shournal_to_snakemake.shell_tokenizer import ShellTokenizer, Token


class ShellTokenizerTest(unittest.TestCase):
    def test_simple(self):
        tokenizer = ShellTokenizer()
        # tokenizer.debug = 1
        cmd = "echo foo bar"
        tokens = tokenizer.split(cmd)

        t1 = Token(string='echo', isSplitter=False, startIdx=0, endIdx=4)
        t2 = Token(string=' ', isSplitter=True, startIdx=4, endIdx=5)
        t3 = Token(string='foo', isSplitter=False, startIdx=5, endIdx=8)
        t4 = Token(string=' ', isSplitter=True, startIdx=8, endIdx=9)
        t5 = Token(string='bar', isSplitter=False, startIdx=9, endIdx=12)

        self.assertEqual([t1, t2, t3, t4, t5], tokens)
        self.assertEqual('echo', cmd[t1.startIdx:t1.endIdx])
        self.assertEqual(' ', cmd[t2.startIdx:t2.endIdx])
        self.assertEqual('foo', cmd[t3.startIdx:t3.endIdx])
        self.assertEqual(' ', cmd[t4.startIdx:t4.endIdx])
        self.assertEqual('bar', cmd[t5.startIdx:t5.endIdx])


    def test_single_quotes_simple(self):
        tokenizer = ShellTokenizer()
        cmd = "echo 'foo' 'bar'"
        tokens = tokenizer.split(cmd)

        # Note: the quotes matter for start-and stopIdx but not for the inner words!
        t1 = Token(string='echo', isSplitter=False, startIdx=0, endIdx=4)
        t2 = Token(string=' ', isSplitter=True, startIdx=4, endIdx=5)
        t3 = Token(string='foo', isSplitter=False, startIdx=5, endIdx=10)
        t4 = Token(string=' ', isSplitter=True, startIdx=10, endIdx=11)
        t5 = Token(string='bar', isSplitter=False, startIdx=11, endIdx=16)

        self.assertEqual([t1, t2, t3, t4, t5], tokens)
        self.assertEqual("echo", cmd[t1.startIdx:t1.endIdx])
        self.assertEqual(' ', cmd[t2.startIdx:t2.endIdx])
        self.assertEqual("'foo'", cmd[t3.startIdx:t3.endIdx])
        self.assertEqual(' ', cmd[t4.startIdx:t4.endIdx])
        self.assertEqual("'bar'", cmd[t5.startIdx:t5.endIdx])


    def test_single_quotes_advanced(self):
        tokenizer = ShellTokenizer()
        cmd = "echo 'foo''bar'''' 'me 'too'"
        tokens = tokenizer.split(cmd)

        t1 = Token(string='echo', isSplitter=False, startIdx=0, endIdx=4)
        t2 = Token(string=' ', isSplitter=True, startIdx=4, endIdx=5)
        t3 = Token(string='foobar me', isSplitter=False, startIdx=5, endIdx=22)
        t4 = Token(string=' ', isSplitter=True, startIdx=22, endIdx=23)
        t5 = Token(string='too', isSplitter=False, startIdx=23, endIdx=28)

        self.assertEqual([t1, t2, t3, t4, t5], tokens)

    def test_escape(self):
        tokenizer = ShellTokenizer()
        cmd = '\\ space\\|./pipe\\>one\\ token'
        tokens = tokenizer.split(cmd)

        t1 = Token(string=' space|./pipe>one token', isSplitter=False, startIdx=0, endIdx=27)
        self.assertEqual([t1], tokens)


    def test_double_quotes_simple(self):
        tokenizer = ShellTokenizer()
        cmd = '"some |text in" " <<double quotes>>"'
        tokens = tokenizer.split(cmd)

        t1 = Token(string='some |text in', isSplitter=False, startIdx=0, endIdx=15)
        t2 = Token(string=' ', isSplitter=True, startIdx=15, endIdx=16)
        t3 = Token(string=' <<double quotes>>', isSplitter=False, startIdx=16, endIdx=36)

        self.assertEqual([t1, t2, t3], tokens)

    def test_double_quotes_recursion(self):
        tokenizer = ShellTokenizer()
        cmd = 'echo "$(echo "one $(echo "two")")"'
        tokens = tokenizer.split(cmd)

        t1 = Token(string='echo', isSplitter=False, startIdx=0, endIdx=4)
        t2 = Token(string=' ', isSplitter=True, startIdx=4, endIdx=5)
        t3 = Token(string=ShellTokenizer.COMMAND_SUBST_PLACEHOLDER, isSplitter=False, startIdx=5, endIdx=34)
        t4 = Token(string='$(', isSplitter=True, startIdx=6, endIdx=8)
        t5 = Token(string='echo', isSplitter=False, startIdx=8, endIdx=12)
        t6 = Token(string=' ', isSplitter=True, startIdx=12, endIdx=13)
        t7 = Token(string='one ' + ShellTokenizer.COMMAND_SUBST_PLACEHOLDER, isSplitter=False, startIdx=13, endIdx=32)
        t8 = Token(string='$(', isSplitter=True, startIdx=18, endIdx=20)
        t9 = Token(string='echo', isSplitter=False, startIdx=20, endIdx=24)
        t10 = Token(string=' ', isSplitter=True, startIdx=24, endIdx=25)
        t11 = Token(string='two', isSplitter=False, startIdx=25, endIdx=30)
        t12 = Token(string=')', isSplitter=True, startIdx=30, endIdx=31)
        t13 = Token(string=')', isSplitter=True, startIdx=32, endIdx=33)

        self.assertEqual([t1, t2, t3, t4, t5, t6, t7,
                          t8, t9, t10, t11, t12, t13], tokens)

    def test_mixed_quotes(self):
        tokenizer = ShellTokenizer()
        cmd = 'foo="double "\'single \'"double \\""\\ noquote'
        tokens = tokenizer.split(cmd)

        t1 = Token(string='foo', isSplitter=False, startIdx=0, endIdx=3)
        t2 = Token(string='=', isSplitter=True, startIdx=3, endIdx=4)
        t3 = Token(string='double single double " noquote', isSplitter=False, startIdx=4, endIdx=42)

        self.assertEqual([t1, t2, t3], tokens)

    def test_mixed_quotes_cmd_subst(self):
        tokenizer = ShellTokenizer()
        cmd = '"$(:)"\'next\''
        tokens = tokenizer.split(cmd)

        t1 = Token(string=ShellTokenizer.COMMAND_SUBST_PLACEHOLDER + 'next', isSplitter=False, startIdx=0, endIdx=12)
        t2 = Token(string='$(', isSplitter=True, startIdx=1, endIdx=3)
        t3 = Token(string=':', isSplitter=False, startIdx=3, endIdx=4)
        t4 = Token(string=')', isSplitter=True, startIdx=4, endIdx=5)

        self.assertEqual([t1, t2, t3, t4], tokens)

    def test_comment(self):
        tokenizer = ShellTokenizer()
        cmd = 'a # stuff \nb c'
        tokens = tokenizer.split(cmd)
        t1 = Token(string='a', isSplitter=False, startIdx=0, endIdx=1)
        t2 = Token(string=' ', isSplitter=True, startIdx=1, endIdx=2)

        t3 = Token(string='b', isSplitter=False, startIdx=11, endIdx=12)
        t4 = Token(string=' ', isSplitter=True, startIdx=12, endIdx=13)
        t5 = Token(string='c', isSplitter=False, startIdx=13, endIdx=14)

        self.assertEqual([t1, t2, t3, t4, t5], tokens)




if __name__ == '__main__':
    unittest.main()
