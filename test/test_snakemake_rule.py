import unittest
from os.path import join as joinpath


from shournal_to_snakemake.snakemake_rule import SnakemakeRule
from shournal_to_snakemake.command import Command, FileReadEvent, FileWriteEvent

def _make_read_event(path):
    _make_read_event.counter += 1
    f = FileReadEvent(id=_make_read_event.counter, path=path, hash=123,
                      size= _make_read_event.counter, isStoredToDisk=False)
    return f

_make_read_event.counter = 0

def _make_write_event(path):
    _make_write_event.counter += 1
    f = FileWriteEvent(id=_make_write_event.counter, path=path, hash=123,
                      size= _make_write_event.counter)
    return f

_make_write_event.counter = 0


def _make_command(cmdstring, workingDir):
    _make_command.counter += 1
    c = Command(command=cmdstring, id = _make_command.counter, workingDir=workingDir,
                fileWriteEvents=[], fileReadEvents=[])
    return c

_make_command.counter = 0


class SnakemakeRuleTest(unittest.TestCase):
    def test_simple(self):
        workingdir = "/home/user"
        r1 = _make_read_event(joinpath(workingdir, 'r1'))
        w1 = _make_write_event(joinpath(workingdir, 'w1'))

        cmd = _make_command("echo hi > w1;cat {}".format(r1.path), workingDir=workingdir )
        cmd.fileReadEvents.append(r1)
        cmd.fileReadEvents.append(w1)
        rule = SnakemakeRule(cmd)

        for f in rule.input:
            self.assertIsNone(f.varnameIO)
        for f in rule.output:
            self.assertIsNone(f.varnameIO)

        self.assertEqual("echo hi > {output};cat {input}", rule.processedCommandString)

    def test_multi(self):
        workingdir = "/home/user"
        r1 = _make_read_event(joinpath(workingdir, 'r1'))
        # spaces should also work...
        r2 = _make_read_event(joinpath(workingdir, 'r 2'))

        r3 = _make_read_event(joinpath(workingdir, 'r 3'))
        w1 = _make_write_event(joinpath(workingdir, 'w1'))

        # test nested double quotes (r 2) and escaped space (r 3)
        cmd = _make_command('echo "$(cat r1 "r 2"   r\\ 3)" > w1', workingDir=workingdir)
        cmd.fileReadEvents = [r1, r2, r3]
        cmd.fileReadEvents.append(w1)
        rule = SnakemakeRule(cmd)

        for f in rule.input:
            self.assertIsNone(f.varnameIO)
        for f in rule.output:
            self.assertIsNone(f.varnameIO)

        self.assertEqual('echo "$(cat {input})" > {output}', rule.processedCommandString)

    def test_vars_simple(self):
        workingdir = "/home/user"
        r1 = _make_read_event(joinpath(workingdir, 'r1'))
        r2 = _make_read_event(joinpath(workingdir, 'r2'))
        w1 = _make_write_event(joinpath(workingdir, 'w1'))
        cmd = _make_command('cat r1;cat r2 > w1', workingDir=workingdir)
        cmd.fileReadEvents = [r1, r2]
        cmd.fileReadEvents.append(w1)
        rule = SnakemakeRule(cmd)

        for f in rule.input:
            self.assertIsNotNone(f.varnameIO)
        for f in rule.output:
            self.assertIsNone(f.varnameIO)

        self.assertEqual('cat {{input.{}}};cat {{input.{}}} > {{output}}'.format(r1.varnameIO, r2.varnameIO)
                         , rule.processedCommandString)




if __name__ == '__main__':
    unittest.main()
