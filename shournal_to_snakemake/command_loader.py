
import logging
from _collections import defaultdict

from shournal_to_snakemake.util import is_subpath

thislogger = logging.getLogger(__name__)


class CommandLoader:

    def __init__(self):
        self.commands = []
        self.cwd = None
        self.pathToReadFiles = None
        self.ignoreWfilesOutsideCwd = True
        self.ignoreRfilesOutsideCwd = False
        # we allow equal command strings with different file events, so
        # store a list of commands for a given command string.
        self._cmdStringCmdsMap = defaultdict(list)

    def maybde_add_command(self, command):
        """
        Add a command to the list, if it
        * matches the working directory AND
        * modified files AND
        * is not a duplicate.
        Drop file events outside the current working directory (cwd), as configured.
        """

        # maybe_todo:
        # it might also be of interest to check file hash to validate that a previously
        # created file is the same as the read one afterwards

        self._discard_duplicate_file_paths(command.fileWriteEvents)
        self._discard_duplicate_file_paths(command.fileReadEvents)

        if not command.fileWriteEvents:
            thislogger.info("ignoring command {}, because it did not modify any files: {}"
                            .format(command.id, command.command))
            return

        # Enforce all commands which modify files to be executed within the same workingDir.
        if self.cwd is not None and command.workingDir != self.cwd:
            thislogger.info("ignoring command {}, because the working directory is not "
                  "{} but {}: {}".format(command.id, self.cwd, command.workingDir, command.command))
            return

        for i in range(len(command.fileWriteEvents) - 1, -1, -1):
            wfile = command.fileWriteEvents[i]
            # Ignore written files outside the working dir or a sub-path?
            # Should usually only be necessary, if the user also observes temporary- or cache-directories
            # (which is not recommended).
            if self.ignoreWfilesOutsideCwd and not is_subpath(wfile.path, command.workingDir):
                thislogger.info("command {}, ignore written filepath {}, because not under working directory {} "
                      .format(command.id, wfile.path, command.workingDir))
                del command.fileWriteEvents[i]


        # we might have deleted all wfiles, so check again:
        if not command.fileWriteEvents:
            thislogger.info("ignoring command {}, because it did not modify any files: {}"
                            .format(command.id, command.command))
            return

        for i in range(len(command.fileReadEvents) - 1, -1, -1):
            rfile = command.fileReadEvents[i]

            if self.ignoreRfilesOutsideCwd and not is_subpath(rfile.path, command.workingDir):
                thislogger.info("command {}, ignore read file-path {}, because not under working directory {} "
                      .format(command.id, rfile.path, command.workingDir))
                del command.fileReadEvents[i]
            # elif rfile.isStoredToDisk:
                # shournal can be configured, to store specific read files within its database
                # (e.g. certain file-extensions (.py, .sh) or mime-types. This typically done
                # for script-files. If that is of interest, the file can be accessed by id using:
                # os.path.join(self.pathToReadFiles, str(rfile.id))
            #   pass

        duplicateCmd = self._find_duplicate_command(command)
        if duplicateCmd is not None:
            thislogger.info("ignoring command {}, because it appears to be a duplicate of command {}: {}"
                            .format(command.id, duplicateCmd.id, command.command))
            return

        if self.cwd is None:
            self.cwd = command.workingDir

        self.commands.append(command)
        self._cmdStringCmdsMap[command.command].append(command)

    def order_by_dependencies(self):
        # maybe_todo:
        # It might be desirable to have
        # the rules in a "natural" order. I'm sure snakemake
        # has the logic already built-in - it might make
        # sense to already check here for cyclic dependencies, etc.
        # The commands are currently sorted by execution start time.
        pass


    def _find_duplicate_command(self, cmd):
        """
        A command is considered equal to another, if the command-string
        and all read and written file-paths are exactly the same.
        :return: the duplicate command or None
        """
        existingCmds = self._cmdStringCmdsMap.get(cmd.command, [])
        for c in existingCmds:
            if set(c.fileWriteEvents) == set(cmd.fileWriteEvents) and \
               set(c.fileReadEvents) == set(cmd.fileReadEvents):
                return c

        return None

    def _discard_duplicate_file_paths(self, fileEvents):
        """
        Because shournal captures file events uniquely by device-inode number and
        not by path, under some circumstances the same path may appear multiple times, e.g.
        in the context of deleting/moving files.
        This is not practical for snakemake -> discard them
        """
        uniquefiles = {}
        for i in range(len(fileEvents) - 1, -1, -1):
            f = fileEvents[i]
            existing = uniquefiles.get(f.path, None)
            if existing is None:
                uniquefiles[f.path] = f
            else:
                thislogger.info("Discarding duplicate file event at path {}".format(f.path))
                del fileEvents[i]