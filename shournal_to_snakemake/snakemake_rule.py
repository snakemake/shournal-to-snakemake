
import os
import sys
import logging
import itertools

from collections import defaultdict
from operator import attrgetter

# pip install ordered-set
from ordered_set import OrderedSet

from shournal_to_snakemake.shell_tokenizer import ShellTokenizer
from shournal_to_snakemake.command import FileReadEvent, FileWriteEvent
from shournal_to_snakemake.shell_tokenizer import Token


thislogger = logging.getLogger()


class SnakemakeRule:
    """
    Transform a command observed by shournal into a Snakemake rule.
    The key-task is to assign the read or input-files and the
    written or output-files which are known from shournal to
    the given paths in the command-string, so the files may
    be referenced by unqualified {input}/{output} or qualified names
    like {input.foo}{output.bar}.
    """

    def __init__(self, command):
        self.command = command
        self._notAssignedFileEvents = []  # read- or write-events without corresponding token.

        self.rulename = "undefined"
        self.rawCommandString = command.command
        # input/ output plain paths will be replaced by variables {input.*, output.*}
        # if we are able to find them in the raw shell command.
        self.processedCommandString = command.command

        tokenizer = ShellTokenizer()

        try:
            tokens = tokenizer.split(command.command)
        except ValueError as e:
            thislogger.warning('Unable to parse shell command {} - {}'.format(command.command, e))
            self.input[:] = [x.path for x in command.fileReadEvents]
            self.output[:] = [x.path for x in command.fileWriteEvents]
            return

        filenameTokensDict = self._build_filename_tokens_dict(tokens)

        # Order of input/output token assignment matters!
        inputFilesNoToken = self._assing_input_tokens( filenameTokensDict, command.fileReadEvents)
        outputFilesNoToken = self._assign_output_tokens( filenameTokensDict, command.fileWriteEvents)

        cmdMeta = self._check_if_IO_qualifiers_needed(tokens)
        # if not all io-files could be assigned use qualifiers anyway:
        if inputFilesNoToken:
            cmdMeta.inputNeedsQualifier = True
        if outputFilesNoToken:
            cmdMeta.outputNeedsQualifier = True

        self.input, self.output = self._generate_IO_variables(inputFilesNoToken,
                                                              outputFilesNoToken, cmdMeta)

        self.processedCommandString = self._generate_command_string_with_IO_vars(cmdMeta)


    def _build_filename_tokens_dict(self, tokens):
        """
        Build a dictionary with possible file-names as key and the corresponding
        tokens as values (the same file-name might appear in multiple tokens).
        A possible file-name is considered the whole token-string, if no path separator
        is found, else the <file-name> of os.path.split(p)
        """

        # a filename might appear in multiple tokens -> defaultdict(list)
        filenameTokensDict = defaultdict(list)
        for token in tokens:
            # dynamically add some meta data field about the token which we need later
            token.attachedFileEvent = None

            if token.isSplitter:
                # only interested in words
                continue

            # ignore trailing slashes
            tokenStr = token.string[:-1] if token.string.endswith('/') else token.string

            # each token is expected to contain at most one path,
            # where we extract the filename (the last entry) from:
            filename = os.path.split(tokenStr)[1]
            if not filename:
                continue
            filenameTokensDict[filename].append(token)

        return filenameTokensDict


    def _assing_input_tokens(self, filenameTokensDict, readEvents):
        """
        Assign file read events to tokens. The same file path may appear in multiple tokens.
        :return set of read events that could not be assigned.
        """
        notFoundEvents = set()
        for file in readEvents:
            matchingTokens = self._findMatchingTokensForPath(filenameTokensDict, file.path,
                                                             self.command.workingDir)
            if not matchingTokens:
                notFoundEvents.add(file)
                continue

            for token in matchingTokens:
                token.attachedFileEvent = file

        return notFoundEvents


    def _assign_output_tokens(self, filenameTokensDict, writeEvents):
        """
        Assign file write events to tokens. This is called, *after* the read events were
        assigned to the tokens. The same file path may appear in multiple tokens.
        If a file path is part of input and output,
        only the final token is considered an output-file.
        :return set of write events that could not be assigned.
        """
        notFoundEvents = set()
        for file in writeEvents:
            matchingTokens = self._findMatchingTokensForPath(filenameTokensDict, file.path,
                                                             self.command.workingDir)
            if not matchingTokens:
                notFoundEvents.add(file)
                continue

            if matchingTokens[0].attachedFileEvent is None:
                for token in matchingTokens:
                    assert token.attachedFileEvent is None
                    token.attachedFileEvent = file
            else:
                # we have already assigned a read event with the same path
                assert isinstance(matchingTokens[0].attachedFileEvent, FileReadEvent) and \
                       matchingTokens[0].attachedFileEvent.path == file.path

                if len(matchingTokens) == 1:
                    thislogger.debug("Output-path skipped: input-event with same path exists, "
                                     "but only one matching token found: {}".format(file.path))
                    notFoundEvents.add(file)
                else:
                    # This is very simplistic: Instead of guessing which token might be in- or output
                    # consider all as input, except the last one.
                    finalToken = max(matchingTokens, key=attrgetter('startIdx'))
                    finalToken.attachedFileEvent = file

        return notFoundEvents


    def _findMatchingTokensForPath(self, filenameTokensDict, path, workingDir):
        matchingTokens = filenameTokensDict.get(os.path.split(path)[1], None)
        if matchingTokens is None:
            return []

        for i in range(len(matchingTokens) - 1, -1, -1):
            t = matchingTokens[i]
            # to abs path, if not already absolute
            resolved = t.string if t.string.startswith('/') else os.path.join(workingDir, t.string)
            resolved = os.path.normpath(resolved)
            if resolved != path:
                thislogger.debug("discarding path «{}» not matching «{}»".format(resolved, path))
                del matchingTokens[i]

        return matchingTokens


    def _check_if_IO_qualifiers_needed(self, tokens):
        """
        Find out whether we can reference all input/output events with a single
        {input/output} or we need qualified {input.f1} (the general case).
        For example
            cat f1 f2 > out1
        would allow to reference f1 and f2 as {input} while
            cat f1 f2 > out; cat out
        requires qualified {input.f1} {input.f2} {input.out}.

        KISS and find the indices of the first and last tokens of each type (input/output).
        Next check, if file-events overlap each other or non-whitespace shell
        splitters are between input/output-tokens

        :param tokens: List of lexical shell tokens with file-events assigned.
        :rtype _CommandMeta
        """
        inputStart = -1
        inputEnd = -1
        outputStart = -1
        outputEnd = -1
        cmdMeta = _CommandMeta()
        for idx in range(len(tokens)):
            t = tokens[idx]
            if t.attachedFileEvent is None:
                continue
            if isinstance(t.attachedFileEvent, FileReadEvent):
                cmdMeta.inputTokens.append(t)
                if inputStart == -1:
                    inputStart = idx
                inputEnd = idx
            else:
                cmdMeta.outputTokens.append(t)
                if outputStart == -1:
                    outputStart = idx
                outputEnd = idx

        if inputStart != -1:
            cmdMeta.inputNeedsQualifier = \
                self._sub_tokens_contain_sep_or_fevent(tokens, inputStart, inputEnd + 1, FileWriteEvent)

        if outputStart != -1:
            cmdMeta.outputNeedsQualifier = \
                self._sub_tokens_contain_sep_or_fevent(tokens, outputStart, outputEnd + 1, FileReadEvent)

        return cmdMeta


    def _sub_tokens_contain_sep_or_fevent(self, tokens, start, stop, fileeventtype):
        """
        :return: True, if the sub-token list contains non-whitespace tokens or
        file-events of type fileeventtype
        """
        for t in itertools.islice(tokens, start, stop):
            if t.attachedFileEvent is not None:
                if type(t.attachedFileEvent) == fileeventtype:
                    return True
            elif not t.string in [' ', '\t', '\n']:
                return True
        return False


    def _generate_IO_variables(self, inputFilesNoToken, outputFilesNoToken,
                               cmdMeta):
        """
        Assign variable names to input and output files. Files for which no token
        could be found come first (implies qualifiers!), others are ordered according to their first occurrence
        in the command-string. In case no qualifiers are needed all variables will be set to None.

        :param inputFilesNoToken: FileReadEvent's for which no token could be found
        :param outputFilesNoToken: FileWriteEvent's for which no token could be found

        :return: (input file events, output file events) in their final order.
        """

        assert not inputFilesNoToken or (inputFilesNoToken and cmdMeta.inputNeedsQualifier)
        assert not outputFilesNoToken or (outputFilesNoToken and cmdMeta.outputNeedsQualifier)

        orderedInputFiles = OrderedSet()
        orderedOutputFiles = OrderedSet()

        inputNotFoundCounter = 0
        for f in inputFilesNoToken:
            f.varnameIO = "in_missing_{}".format(inputNotFoundCounter)
            orderedInputFiles.add(f)
            inputNotFoundCounter += 1

        outputNotFundCounter = 0
        for f in outputFilesNoToken:
            f.varnameIO = "out_missing_{}".format(outputNotFundCounter)
            orderedOutputFiles.add(f)
            outputNotFundCounter += 1

        inputCounter = 0
        for t in cmdMeta.inputTokens:
            if not t.attachedFileEvent in orderedInputFiles:
                t.attachedFileEvent.varnameIO = \
                    "in_{}".format(inputCounter) if cmdMeta.inputNeedsQualifier else None
                orderedInputFiles.add(t.attachedFileEvent)
                inputCounter += 1

        outputCounter = 0
        for t in cmdMeta.outputTokens:
            if not t.attachedFileEvent in orderedOutputFiles:
                t.attachedFileEvent.varnameIO = \
                    "out_{}".format(outputCounter) if cmdMeta.outputNeedsQualifier else None
                orderedOutputFiles.add(t.attachedFileEvent)
                outputCounter += 1

        return orderedInputFiles, orderedOutputFiles


    def _generate_command_string_with_IO_vars(self, cmdMeta):
        """
        Replace all found paths in the command-string with either unqualified
        {input/output} (if all input file-paths occurred in a row) or qualified
        {intput.f1/output.f2} variables and return the new command string.
        """
        # _dbg_print_tokens(cmdMeta.inputTokens)
        # _dbg_print_tokens(cmdMeta.outputTokens)

        replaceTokens = []
        if cmdMeta.inputNeedsQualifier:
            replaceTokens.extend(cmdMeta.inputTokens)
        else:
            if cmdMeta.inputTokens:
                # No qualifiers needed; replace all input tokens with {input}
                replaceTokens.append(_UnqualifiedToken(cmdMeta.inputTokens))

        if cmdMeta.outputNeedsQualifier:
            replaceTokens.extend(cmdMeta.outputTokens)
        else:
            if cmdMeta.outputTokens:
                replaceTokens.append(_UnqualifiedToken(cmdMeta.outputTokens))

        # we <replace> stuff in a string, do it from backwards
        replaceTokens.sort(key=lambda t: t.startIdx, reverse=True)

        newCommandStr = self.command.command
        lastStartIdx = sys.maxsize
        for t in replaceTokens:
            # TODO:
            #  rather warning than assert? Could that happen in case
            #  of recursive double-quote resolution?
            assert t.endIdx < lastStartIdx and t.startIdx < t.endIdx

            if isinstance(t, _UnqualifiedToken):
                inputOrOutput = "{input}" if t.isInput else "{output}"
                newCommandStr = newCommandStr[:t.startIdx] + inputOrOutput \
                                 + newCommandStr[t.endIdx:]
            else:
                inputOrOutput = "input" if isinstance(t.attachedFileEvent, FileReadEvent) else "output"
                newCommandStr = newCommandStr[:t.startIdx] +\
                                "{" + inputOrOutput + "." + t.attachedFileEvent.varnameIO + "}" + \
                                    newCommandStr[t.endIdx:]
            lastStartIdx = t.startIdx

        return newCommandStr


class _UnqualifiedToken(Token):
    """
    A token belonging to one or multiple filename-tokens which occur
    in a row (without non-whitespace-splitters), thus reaching from the startIdx of the first single
    token to the endIdx of the last.
    """
    def __init__(self, tokenlist):
        super().__init__(string="", isSplitter=False,
                         startIdx=tokenlist[0].startIdx, endIdx=tokenlist[-1].endIdx)
        # else output
        self.isInput = isinstance(tokenlist[0].attachedFileEvent, FileReadEvent)


class _CommandMeta:
    def __init__(self):
        # All tokens with belonging input event, naturally ordered by occurrence
        # in the command string
        self.inputTokens = []
        self.outputTokens = []

        self.inputNeedsQualifier = False
        self.outputNeedsQualifier = False


def _dbg_print_tokens(tokens):
    for t in tokens:
        thislogger.debug("token", t.string, t.attachedFileEvent.path)