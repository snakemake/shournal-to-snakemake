"""
Representation of a shournal command and corresponding file-events
(read/write).
"""


class Command:

    def __init__(self, id=None, command=None, returnValue=None, username=None,
                 hostname=None, hashChunkSize=None, hashMaxCountOfReads=None,
                 sessionUuid=None, startTime=None, endTime=None,
                 workingDir=None, fileReadEvents=None, fileWriteEvents=None):
        """
        :param id: id in shournal's database
        :param command: raw command-string as reported by the shell's history (variables not resolved)
        :param returnValue: $?
        :param username: ^_^
        :param hostname: ^_^
        :param hashChunkSize: setting for partial file hash
        :param hashMaxCountOfReads: setting for partial file hash
        :param sessionUuid: uuid of a particular shell session
        :param startTime: when did the command start
        :param endTime: when did the command end
        :param workingDir: ^_^
        :param fileReadEvents: array of FileReadEvent
        :param fileWriteEvents: array of FileWriteEvent
        """
        self.id = id
        self.command = command
        self.returnValue = returnValue
        self.username = username
        self.hostname = hostname
        self.hashChunkSize = hashChunkSize
        self.hashMaxCountOfReads = hashMaxCountOfReads
        self.sessionUuid = sessionUuid
        self.startTime = startTime
        self.endTime = endTime
        self.workingDir = workingDir

        self.fileReadEvents = fileReadEvents
        self.fileWriteEvents = fileWriteEvents


    @classmethod
    def from_json(cls, rawJson):
        cmd = Command()
        cmd.__dict__ = rawJson

        # Also resolve the nested json-arrays of read- and write-file events
        for i in range(len(cmd.fileReadEvents)):
            f = FileReadEvent()
            f.__dict__ = cmd.fileReadEvents[i]
            cmd.fileReadEvents[i] = f

        for i in range(len(cmd.fileWriteEvents)):
            f = FileWriteEvent()
            f.__dict__ = cmd.fileWriteEvents[i]
            cmd.fileWriteEvents[i] = f

        return cmd


    def __eq__(self, other):
        if isinstance(other, Command):
            return self.id == other.id
        return NotImplemented

    def __hash__(self):
        return self.id


class FileWriteEvent:
    def __init__(self, id=None, path=None, size=None, mtime=None, hash=None):
        self.id = id
        self.path = path
        self.size = size
        self.mtime = mtime
        self.hash = hash

    def __eq__(self, other):
        if isinstance(other, FileWriteEvent):
            return self.path == other.path
        elif isinstance(other, FileReadEvent):
            return False
        return NotImplemented

    def __hash__(self):
        return hash(self.path)


class FileReadEvent:
    def __init__(self, id=None, path=None, size=None, mtime=None, hash=None, isStoredToDisk=None):
        self.id = id
        self.path = path
        self.size = size
        self.mtime = mtime
        self.hash = hash
        self.isStoredToDisk = isStoredToDisk

    def __eq__(self, other):
        if isinstance(other, FileReadEvent):
            return self.path == other.path
        elif isinstance(other, FileWriteEvent):
            return False

        return NotImplemented

    def __hash__(self):
        return hash(self.path)
