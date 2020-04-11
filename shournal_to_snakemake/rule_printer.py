

from shournal_to_snakemake.util import is_subpath

class RulePrinter:

    def __init__(self):
        self.indent1 = " " * 4
        self.indent2 = self.indent1 * 2

    def print(self, rule):
        """
        :param rule: the snakemake rule to print
        :type rule: SnakemakeRule
        """
        # TODO: wrap long IO-paths and commands to next line
        print("rule", rule.rulename + ":")

        if rule.input:
            print("{}input:".format(self.indent1))
            for f in rule.input:
                self._print_file_at_indent(self.indent2, f, rule.command)

        if rule.output:
            print("{}output:".format(self.indent1))
            for f in rule.output:
                self._print_file_at_indent(self.indent2, f, rule.command)

        print("{}shell:".format(self.indent1))
        print('{}# raw: {}'.format(self.indent2, rule.rawCommandString))
        print('{}{}'.format(self.indent2, self._escape_and_quote(rule.processedCommandString)))

        print('\n')


    def _print_file_at_indent(self, indent, f, command):
        # use relative paths if below working dir
        path = f.path[len(command.workingDir) + 1:] \
            if is_subpath(f.path, command.workingDir) \
            else f.path
        varnameStr = '' if f.varnameIO is None else f.varnameIO + '='
        # KISS: always trailing comma
        print('{}{}{},'.format(indent, varnameStr, self._escape_and_quote(path)))

    def _escape_and_quote(self, string, quotechar='"'):
        """
        Wrap a given string into quotes, escape as necessary, e.g. «echo "foo"» -> «"echo \"foo\"».
        Backslash '\' is also be escaped.

        :param string: e.g. path or command string
        :param quotechar: type of outer quote character of the rule, that is either ' or "
        :return: the quoted and escaped string.
        """
        escaped = string.replace("\\", "\\\\")
        escaped = escaped.replace(quotechar, '\\' + quotechar)
        return quotechar + escaped + quotechar
