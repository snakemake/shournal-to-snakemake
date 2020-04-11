

import sys
import json
import logging
import argparse

from shournal_to_snakemake.command_loader import CommandLoader
from shournal_to_snakemake.util import eprint, SimpleJsonToObject
from shournal_to_snakemake.snakemake_rule import SnakemakeRule
from shournal_to_snakemake.command import Command
from shournal_to_snakemake import app, __version__
from shournal_to_snakemake.rule_printer import RulePrinter
from shournal_to_snakemake.argparse_helpers import ActionNoYes


def real_main():
    parser = argparse.ArgumentParser(
        description='Transform a command series observed by shournal to snakemake rules. '
                    'shournal tracks read and written files of shell commands. Thus, for '
                    'each command the input- and output-section  of a snakemake rule may be generated. '
                    'Matched file-paths are automatically replaced in the command string with '
                    '{input} and {output}',
        usage='shournal --query --output-format json --history 3 | {0} [options]\n'
              'Alternatively read from a file:\n'
              '{0} [options] FILE\n'.format(app.APP_NAME),
    )

    parser.add_argument('--version', action='version', version='{} {}'.format(app.APP_NAME, __version__))
    parser.add_argument('--log-level',
                        choices=['debug', 'info', 'warning', 'error'],
                        default='warning',
                        help='Set the log-level of the application')

    RFILES_OUTSIDE_CWD = True
    parser.add_argument('--rfiles-outside-cwd', action=ActionNoYes, default=RFILES_OUTSIDE_CWD,
                        help='Specify whether *read* file events which occurred outside the working directory '
                             '(or its sub-paths) shall be added to the input-section of the rule. Default is {}'
                             .format(RFILES_OUTSIDE_CWD)
                        )

    WFILES_OUTSIDE_CWD = False
    parser.add_argument('--wfiles-outside-cwd', action=ActionNoYes, default=WFILES_OUTSIDE_CWD,
                        help='Specify whether *written* file events which occurred outside the working directory '
                             '(or its sub-paths) shall be added to the output-section of the rule. Default is {}'
                        .format(WFILES_OUTSIDE_CWD)
                        )

    # The overall working dir for *all rules* is taken from the first accepted command. If that is not the
    # desired working dir, specify it using shournal's --query -cwd argument.
    # Therefor it's not necessary to duplicate the cwd argument here(parser.add_argument('--working-dir'))

    parsed_args, unknown_args = parser.parse_known_args(sys.argv[1:])
    cmdLoader = CommandLoader()

    loglevel = getattr(logging, parsed_args.log_level.upper())
    logging.basicConfig(level=loglevel, format='snakemake-plugin-shournal: %(levelname)s: %(message)s')

    cmdLoader.ignoreRfilesOutsideCwd = not parsed_args.rfiles_outside_cwd
    cmdLoader.ignoreWfilesOutsideCwd = not parsed_args.wfiles_outside_cwd

    inputDev = sys.stdin
    if unknown_args:
        if len(unknown_args) != 1:
            eprint("Expected exactly one input file but received", unknown_args)
            exit(1)

        # dash: read from stdin
        if unknown_args[0] != '-':
            try:
                inputDev = open(unknown_args[0], 'r')
            except OSError as e:
                eprint("Failed to open input file:", e)
                exit(1)

    header = inputDev.readline()
    if not header:
        eprint("No input given")
        exit(1)

    header = header.rstrip()
    if not header.startswith('HEADER:'):
        eprint("Unable to parse shournal's output - please make sure to use the json output format, e.g. "
               "shournal --query --output-format json --history 5")
        exit(1)
    header = json.loads(header[len('HEADER:'):])
    header = SimpleJsonToObject(header)

    cmdLoader.pathToReadFiles = header.pathToReadFiles

    for line in inputDev:
        line = line.rstrip()
        if(line.startswith('COMMAND:')):
            rawJsonCmd = json.loads(line[len('COMMAND:'):])
            cmd = Command.from_json(rawJsonCmd)
            cmdLoader.maybde_add_command(cmd)
        else:
            assert line.startswith('FOOTER:')
            # footer = SimpleJsonToObject( json.loads(line[len('FOOTER:'):]))

    cmdLoader.order_by_dependencies()

    ruleCounter = 0
    rulePrinter = RulePrinter()
    for cmd in cmdLoader.commands:
        rule = SnakemakeRule(cmd)
        ruleCounter += 1
        rule.rulename = "undefined_{}".format(ruleCounter)
        rulePrinter.print(rule)


def main():
    try:
        real_main()
    except KeyboardInterrupt:
        pass


if __name__ == '__main__':
    main()



