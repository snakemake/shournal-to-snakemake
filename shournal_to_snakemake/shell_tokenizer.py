
from shournal_to_snakemake.abstract_class_helpers import SimpleEquality

class Token(SimpleEquality):
    def __init__(self, string, isSplitter, startIdx, endIdx=-1):
        """
        :param string: if a splitter, the raw splitting string, if a word, the unescaped unsubstituted string.
        :param isSplitter: True, if a non-escaped character sequence that separates words, like
                           | & or control operators like && ||
        :param startIdx: the start index of the token *including* possible quotes or leading backslashes.
        :param endIdx: the end index of the token *including* trailing quotes. The endIdx is *exclusive*
                       so it can be used for pythons slice [start:stop] easily.
        """
        if isSplitter:
            # endIdx should be known beforehand in that case
            assert endIdx != -1
        # note: for cases like
        # ls foo'''bar'
        # -> len(self.string) != endIdx - startIdx
        self.string = string
        self.startIdx = startIdx # in original string, including the token
        self.endIdx = endIdx
        self.isSplitter = isSplitter


class ShellTokenizer:
    """
    A poor man's parser to tokenize basic shell commands.
    Why not using shlex? Because it exposes no information where exactly the token came from.
    Further shlex does not correctly support parenthesis and nested
    double-quotes, e.g foo="$(echo "bar")".
    maybe_todo: also support $'string' (see man bash)
    """
    # If command-substitution occurs within double-quotes (or backticks) it is replaced
    # in the resolved outer token with the following sequence:
    COMMAND_SUBST_PLACEHOLDER = '$(...)'

    def __init__(self):
        self.comand = "" # the raw command-sequence passed on split
        self.idx = 0
        self.tokens = []
        # splitters with one char
        self.splitters1 = {'|', '&', ';', '(', ')', '=', '<', '>', ' ', '\t', '\n', '`'}
        # splitters with two chars
        self.splitters2 = { '||', '&&', ';;', ';&',
                            '|&', '>>', '<<', '$(' }
        self.escapes1 = {'\\'}
        self.comments = {'#'}
        self.debug = 0


    def split(self, s):
        self.comand = s
        return self._private_split(closingString=None)


    def _private_split(self, closingString):
        if closingString is not None:
            assert len(closingString) == 1

        startIdx = self.idx

        token = None
        escapeSeen = False
        while self.idx < len(self.comand):
            current=self.comand[self.idx]
            next = None if self.idx >= len(self.comand) - 1 else self.comand[self.idx+1]
            currentAndNext = None if next is None else current + next

            if escapeSeen:
                self._logdbg('was previously escaped: «{}»'.format(current))
                assert token is not None
                # the last character was escaped -> append current
                token.string += current
                escapeSeen = False
            elif current in self.escapes1:
                self._logdbg('escape-char: «{}»'.format(current))
                if token is None:
                    token = self._createAppendToken("", isSplitter=False, startIdx=self.idx)
                else:
                    assert not token.isSplitter
                escapeSeen = True
            elif closingString is not None and current == closingString:
                self._logdbg('found closing string: «{}»'.format(closingString))
                # return from double-quote command-substitution recursion
                self._finalizeTokenIfAny(token)
                token = None
                self._createAppendToken(string=closingString, isSplitter=True, startIdx=self.idx, endIdx=self.idx + len(closingString))
                return
            elif current == "'":
                if token is None:
                    token = self._createAppendToken('', isSplitter=False, startIdx=self.idx)
                # else: append the string between the quotes to the previous token.
                # This also covers cases like echo abc'de'fg'hij'.
                self._handle_singlequote(token)
            elif current == '"':
                if token is None:
                    token = self._createAppendToken('', isSplitter=False, startIdx=self.idx)
                # else: see else-comment for handling for single quotes
                self._handle_doublequotes(token)
            # be greedy and first try to consume two splitters, then one.
            elif currentAndNext is not None and currentAndNext in self.splitters2:
                self._finalizeTokenIfAny(token)
                token = None
                self._createAppendToken(string=currentAndNext, isSplitter=True, startIdx=self.idx, endIdx=self.idx + 2)
                # consumed two chars: (idx is incremented also below at loop end)
                self.idx += 1
            elif current in self.splitters1:
                self._finalizeTokenIfAny(token)
                token = None
                self._createAppendToken(string=current, isSplitter=True, startIdx=self.idx, endIdx=self.idx + 1)
            elif current in self.comments:
                self._finalizeTokenIfAny(token)
                token = None
                self._handleComment()
            else:
                # collect that char for current token
                if token is None:
                    token = self._createAppendToken(string=current, isSplitter=False, startIdx=self.idx)
                else:
                    assert not token.isSplitter
                    token.string += current

            self.idx += 1

        if closingString is not None:
            raise ValueError(
                "missing closing «{}» started near index {}: {}".format(closingString, startIdx, self.comand[startIdx:]))

        # handle the final token, if any
        self._finalizeTokenIfAny(token)
        return self.tokens

    def _createAppendToken(self, *args, **kwargs):
        token = Token(*args, **kwargs)
        self.tokens.append(token)
        return token

    def _finalizeTokenIfAny(self, token):
        """
        To be called when a new splitter was detected -> the new splitter shall
        not be part of the token, so end-idx is self.idx-1
        :param token:
        :return:
        """
        if token is None:
            return
        self._logdbg("finalizing token: {}".format(token.string))
        assert token.startIdx >= 0
        assert token.startIdx < self.idx
        token.endIdx = self.idx

    def _handleComment(self):
        self.idx += 1
        while self.idx < len(self.comand):
            current = self.comand[self.idx]
            # comments end on newline
            if current == '\n':
                return
            self.idx += 1

    def _handle_singlequote(self, token):
        """
         The most simple case -> do not interpret anything until we hit
         another single quote. Following bash, no escaping is possible,
         also not single-quotes!

        :raises ValueError
        """
        startIdx = self.idx
        self.idx += 1
        while self.idx < len(self.comand):
            current = self.comand[self.idx]
            if current == "'":
                # do not set startidx here, we might be appending to a previous token!
                token.string += self.comand[startIdx + 1:self.idx]
                return
            self.idx += 1

        raise ValueError("missing closing singlequotes started at index {}: {}".format(startIdx, self.comand[startIdx:]))

    def _handle_doublequotes(self, token):
        """
        Quoting bash v4.4 manual:
        >> Enclosing characters in double quotes preserves the  literal  value  of
        >> all  characters  within the quotes, with the exception of $, `, \, and,
        >> when history expansion is enabled, !
        (we ignore history expansion here).
        ...
        >> The backslash retains its special meaning
        >> only when followed by one of the following characters: $, `, ",  \,
        >> or  <newline>.

        As a consequence since we may not execute commands, nor do we resolve variables,
        only tokenize command-substitutions $( and `

        :raises ValueError
        """

        startIdx = self.idx
        # we treat everything within the double-quotes as a single token *except* text between command-substitution
        # (and escaped chars) -> append all text outside command-substitution to the token. As a result, the self.tokens-list
        # will first contain the outer double quoted strings and then possibly inner tokens (recursion!).
        escapeSeen = False
        self.idx += 1
        while self.idx < len(self.comand):
            current = self.comand[self.idx]
            next = None if self.idx >= len(self.comand) - 1 else self.comand[self.idx + 1]
            currentAndNext = None if next is None else current + next

            if escapeSeen:
                self._logdbg('was previously escaped: {}'.format(current))
                # the last character was escaped -> append current
                token.string += current
                escapeSeen = False
            elif current == '\\':
                if next in {'$', '`', '"',  '\\'}:
                    self._logdbg('escape-char: {}'.format(current))
                    escapeSeen = True
                else:
                    token.string += current
            elif currentAndNext is not None and currentAndNext == '$(':
                # make it clear in the outer token that command-substitution occurred
                token.string += ShellTokenizer.COMMAND_SUBST_PLACEHOLDER
                self._createAppendToken(string=currentAndNext, isSplitter=True, startIdx=self.idx, endIdx=self.idx + len(currentAndNext))
                self.idx += 2
                self._private_split(closingString=')')
            elif current == '`':
                # make it clear in the outer token that command-substitution occurred
                token.string += ShellTokenizer.COMMAND_SUBST_PLACEHOLDER
                self._createAppendToken(string=current, isSplitter=True, startIdx=self.idx, endIdx=self.idx + len(current))
                self.idx += 1
                self._private_split(closingString='`')
            elif current == '"':
                # remember that the token might *not* be at the back of self.tokens if command-subst. occurred.
                return
            else:
                token.string += current
            self.idx += 1
        raise ValueError(
            "missing closing doublequotes started at index {}: {}".format(startIdx, self.comand[startIdx:]))



    def _logdbg(self, msg, loglvl=1):
        if self.debug >= loglvl:
            print('ShellTokenizer debug:', msg)










