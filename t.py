#!/usr/bin/env python

"""t is for people that want do things, not organize their tasks."""

from __future__ import with_statement, print_function

import os, re, sys, hashlib, time
from operator import itemgetter
from optparse import OptionParser, OptionGroup
import json

class InvalidTaskfile(Exception):
    """Raised when the path to a task file already exists as a directory."""
    pass

class AmbiguousPrefix(Exception):
    """Raised when trying to use a prefix that could identify multiple tasks."""
    def __init__(self, prefix):
        super(AmbiguousPrefix, self).__init__()
        self.prefix = prefix

class UnknownPrefix(Exception):
    """Raised when trying to use a prefix that does not match any tasks."""
    def __init__(self, prefix):
        super(UnknownPrefix, self).__init__()
        self.prefix = prefix

class BadFile(Exception):
    """Raised when something else goes wrong trying to work with the task file."""
    def __init__(self, path, problem):
        super(BadFile, self).__init__()
        self.path = path
        self.problem = problem

def _hash(text):
    """Return a hash of the given text for use as an id.

    Currently SHA1 hashing is used.  It should be plenty for our purposes.

    """
    return hashlib.sha1((str(time.time()) + text).encode('utf-8')).hexdigest()

def _task_from_taskline(taskline):
    """Parse a taskline (from a task file) and return a task.

    A taskline should be in the format:

        summary text ... | {json of metadata}

    The task returned will be a dictionary such as:

        { 'id': <hash id>,
          'text': <summary text>,
           ... other metadata ... }

    A taskline can also consist of only summary text, in which case the id
    and other metadata will be generated when the line is read.  This is
    supported to enable editing of the taskfile with a simple text editor.
    """
    if taskline.strip().startswith('#'):
        return None
    elif '|' in taskline:
        text, _, meta = taskline.partition('|')
        task = json.loads(meta)
        task['text'] = text.strip()
    else:
        text = taskline.strip()
        task = { 'id': _hash(text), 'text': text }

    if 'timestamp' not in task:
        task['timestamp'] = 0

    if 'show_full_id' not in task:
        task['show_full_id'] = False

    if 'parent_id' not in task:
        task['parent_id'] = None

    return task

def _tasklines_from_tasks(tasks):
    """Parse a list of tasks into tasklines suitable for writing."""

    tasklines = []

    textlen = max(map(lambda t: len(t['text']), tasks)) if tasks else 0

    for task in tasks:
        meta = dict(task)

        # remove text as it isn't part of the metadata
        del meta['text']

        # don't add show_full_id if it is false
        if 'show_full_id' in meta and not meta['show_full_id']:
            del meta['show_full_id']

        # don't add parent_id if it is None
        if 'parent_id' in meta and meta['parent_id'] == None:
            del meta['parent_id']

        tasklines.append('%s | %s\n' % (task['text'].ljust(textlen), json.dumps(meta, sort_keys=True)))

    return tasklines

def _prefixes(ids):
    """Return a mapping of ids to prefixes in O(n) time.

    Each prefix will be the shortest possible substring of the ID that
    can uniquely identify it among the given group of IDs.

    If an ID of one task is entirely a substring of another task's ID, the
    entire ID will be the prefix.
    """
    ps = {}
    for id in ids:
        id_len = len(id)
        for i in range(1, id_len+1):
            # identifies an empty prefix slot, or a singular collision
            prefix = id[:i]
            if (not prefix in ps) or (ps[prefix] and prefix != ps[prefix]):
                break
        if prefix in ps:
            # if there is a collision
            other_id = ps[prefix]
            for j in range(i, id_len+1):
                if other_id[:j] == id[:j]:
                    ps[id[:j]] = ''
                else:
                    ps[other_id[:j]] = other_id
                    ps[id[:j]] = id
                    break
            else:
                ps[other_id[:id_len+1]] = other_id
                ps[id] = id
        else:
            # no collision, can safely add
            ps[prefix] = id
    ps = dict(zip(ps.values(), ps.keys()))
    if '' in ps:
        del ps['']
    return ps


class TaskDict(object):
    """A set of tasks, both finished and unfinished, for a given list.

    The list's files are read from disk when the TaskDict is initialized. They
    can be written back out to disk with the write() function.

    """
    def __init__(self, taskdir='.', name='tasks'):
        """Initialize by reading the task files, if they exist."""
        self.tasks = {}
        self.done = {}
        self.name = name
        self.taskdir = taskdir
        filemap = (('tasks', self.name), ('done', '.%s.done' % self.name))
        for kind, filename in filemap:
            path = os.path.join(os.path.expanduser(self.taskdir), filename)
            if os.path.isdir(path):
                raise InvalidTaskfile
            if os.path.exists(path):
                try:
                    with open(path, 'r') as tfile:
                        tls = [tl.strip() for tl in tfile if tl]
                        tasks = map(_task_from_taskline, tls)
                        for task in tasks:
                            if task is not None:
                                getattr(self, kind)[task['id']] = task
                except IOError as e:
                    raise BadFile(path, e.strerror)

    def __getitem__(self, prefix):
        """Return the unfinished task with the given prefix.

        If more than one task matches the prefix an AmbiguousPrefix exception
        will be raised, unless the prefix is the entire ID of one task.

        If no tasks match the prefix an UnknownPrefix exception will be raised.

        """
        matched = [tid for tid in self.tasks.keys() if tid.startswith(prefix)]
        if len(matched) == 1:
            return self.tasks[matched[0]]
        elif len(matched) == 0:
            raise UnknownPrefix(prefix)
        elif prefix in matched:
            return self.tasks[prefix]
        else:
            raise AmbiguousPrefix(prefix)

    def add_task(self, text, verbose, quiet, task_id = None, parent_id = None):
        """Add a new, unfinished task with the given summary text."""
        if not task_id:
            task_id = _hash(text)
            show_full_id = False
        else:
            show_full_id = True

        if parent_id:
            parent = self[parent_id]
            parent_id = parent['id']

        timestamp = time.time()
        self.tasks[task_id] = {'id': task_id, 'text': text, 'timestamp': timestamp}

        if show_full_id:
            self.tasks[task_id]['show_full_id'] = show_full_id

        if parent_id:
            self.tasks[task_id]['parent_id'] = parent_id

        if not quiet:
            if verbose or show_full_id:
                print(task_id)
            else:
                prefixes = _prefixes(self.tasks)
                print(prefixes[task_id])

    def edit_task(self, prefix, text):
        """Edit the task with the given prefix.

        If more than one task matches the prefix an AmbiguousPrefix exception
        will be raised, unless the prefix is the entire ID of one task.

        If no tasks match the prefix an UnknownPrefix exception will be raised.

        """
        task = self[prefix]
        if text.startswith('s/') or text.startswith('/'):
            text = re.sub('^s?/', '', text).rstrip('/')
            find, _, repl = text.partition('/')
            text = re.sub(find, repl, task['text'])

        task['text'] = text
        if 'id' not in task:
            task['id'] = _hash(text)

    def add_tag(self, task, tag):
        """Add tag to the the task with the given prefix.

        If more than one task matches the prefix an AmbiguousPrefix exception
        will be raised, unless the prefix is the entire ID of one task.

        If no tasks match the prefix an UnknownPrefix exception will be raised.

        """
        if 'tags' in task:
            task['tags'].append(tag)
        else:
            task['tags'] = [tag]

    def remove_tag(self, task, tag):
        """Remove tag to the the task with the given prefix.

        If more than one task matches the prefix an AmbiguousPrefix exception
        will be raised, unless the prefix is the entire ID of one task.

        If no tasks match the prefix an UnknownPrefix exception will be raised.

        """
        if 'tags' in task:
            task['tags'].remove(tag)

        if len(task['tags']) == 0:
            del task['tags']

    def tag(self, prefix, tags):
        """Add (or remove) tag to the the task with the given prefix.

        If more than one task matches the prefix an AmbiguousPrefix exception
        will be raised, unless the prefix is the entire ID of one task.

        If no tasks match the prefix an UnknownPrefix exception will be raised.

        """

        task = self[prefix]
        for tag in tags.strip().split(' '):
            if not tag:
                continue
            elif tag[0] == '-':
                self.remove_tag(task, tag[1:])
            else:
                self.add_tag(task, tag)

    def children(self, task):
        return [self.tasks[t] for t in self.tasks if 'parent_id' in self.tasks[t] and self.tasks[t]['parent_id'] == task['id']]

    def num_children(self, task):
        return len(self.children(task))

    def finish_task(self, prefix, force = False):
        """Mark the task with the given prefix as finished.

        If more than one task matches the prefix an AmbiguousPrefix exception
        will be raised, if no tasks match it an UnknownPrefix exception will
        be raised.

        """

        if not force and self.num_children(self[prefix]) > 0:
            print('cannot finish task - it has open sub-tasks. use --force to override.\n')
            return

        task = self.tasks.pop(self[prefix]['id'])
        self.done[task['id']] = task

        for child in self.children(task):
            self.finish_task(child['id'])

    def remove_task(self, prefix):
        """Remove the task from tasks list.

        If more than one task matches the prefix an AmbiguousPrefix exception
        will be raised, if no tasks match it an UnknownPrefix exception will
        be raised.

        """
        self.tasks.pop(self[prefix]['id'])


    def print_list(self, kind='tasks', verbose=False, quiet=False, grep='', parent_id=None, indent=""):
        """Print out a nicely formatted list of unfinished tasks."""
        tasks = dict(getattr(self, kind).items())
        label = 'prefix' if not verbose else 'id'

        if not verbose:
            for task_id, prefix in _prefixes(tasks).items():
                if tasks[task_id]['show_full_id']:
                    tasks[task_id]['prefix'] = task_id
                else:
                    tasks[task_id]['prefix'] = prefix

        plen = max(map(lambda t: len(t[label]), tasks.values())) if tasks else 0
        for task in sorted(tasks.values(), key=lambda t:t['timestamp']):
            if grep.lower() in task['text'].lower():
                if parent_id == task['parent_id']:
                    num_str = "(%d) " % self.num_children(task)
                    p = '%s - ' % task[label].ljust(plen) if not quiet else ''
                    if 'tags' in task:
                        tags_str = " ".join(["[%s]" % tag for tag in task['tags']]) + " "
                    else:
                        tags_str = ""
                    print(indent + num_str + p + tags_str + task['text'])
                    self.print_list(kind, verbose, quiet, grep, task['id'], indent + "  ")

    def write(self, delete_if_empty=False):
        """Flush the finished and unfinished tasks to the files on disk."""
        filemap = (('tasks', self.name), ('done', '.%s.done' % self.name))
        for kind, filename in filemap:
            path = os.path.join(os.path.expanduser(self.taskdir), filename)
            if os.path.isdir(path):
                raise InvalidTaskfile
            tasks = sorted(getattr(self, kind).values(), key=itemgetter('id'))
            if tasks or not delete_if_empty:
                try:
                    with open(path, 'w') as tfile:
                        for taskline in _tasklines_from_tasks(tasks):
                            tfile.write(taskline)
                except IOError as e:
                    raise BadFile(path, e.strerror)

            elif not tasks and os.path.isfile(path):
                os.remove(path)


def _die(message):
    sys.stderr.write('error: %s\n' % message)
    sys.exit(1)

def _build_parser():
    """Return a parser for the command-line interface."""
    usage = "Usage: %prog [-t DIR] [-l LIST] [options] [TEXT]"
    parser = OptionParser(usage=usage)

    actions = OptionGroup(parser, "Actions",
        "If no actions are specified the TEXT will be added as a new task.")
    actions.add_option("-a", "--add", dest="add", default="",
                       help="add TASK with TEXT", metavar="TASK")
    actions.add_option("-e", "--edit", dest="edit", default="",
                       help="edit TASK to contain TEXT", metavar="TASK")
    actions.add_option("-f", "--finish", dest="finish",
                       help="mark TASK as finished", metavar="TASK")
    actions.add_option("-r", "--remove", dest="remove",
                       help="Remove TASK from list", metavar="TASK")
    actions.add_option("-s", "--sub", dest="sub",
                       help="add sub task to PARENT", metavar="PARENT")
    actions.add_option("-x", "--tag", dest="tag",
                       help="add tag to TASK", metavar="TASK")
    actions.add_option("--force",
                       action="store_true", dest="force", default=False,
                       help="used to force an action even if it is not recommended")
    parser.add_option_group(actions)

    config = OptionGroup(parser, "Configuration Options")
    config.add_option("-l", "--list", dest="name", default="tasks",
                      help="work on LIST", metavar="LIST")
    config.add_option("-t", "--task-dir", dest="taskdir", default="",
                      help="work on the lists in DIR", metavar="DIR")
    config.add_option("-d", "--delete-if-empty",
                      action="store_true", dest="delete", default=False,
                      help="delete the task file if it becomes empty")
    parser.add_option_group(config)

    output = OptionGroup(parser, "Output Options")
    output.add_option("-g", "--grep", dest="grep", default='',
                      help="print only tasks that contain WORD", metavar="WORD")
    output.add_option("-v", "--verbose",
                      action="store_true", dest="verbose", default=False,
                      help="print more detailed output (full task ids, etc)")
    output.add_option("-q", "--quiet",
                      action="store_true", dest="quiet", default=False,
                      help="print less detailed output (no task ids, etc)")
    output.add_option("--done",
                      action="store_true", dest="done", default=False,
                      help="list done tasks instead of unfinished ones")
    parser.add_option_group(output)

    return parser

def _main():
    """Run the command-line interface."""
    (options, args) = _build_parser().parse_args()

    td = TaskDict(taskdir=options.taskdir, name=options.name)
    text = ' '.join(args).strip()

    if '\n' in text:
        _die('task text cannot contain newlines')

    try:
        if options.finish:
            td.finish_task(options.finish, force=options.force)
            td.write(options.delete)
        elif options.remove:
            td.remove_task(options.remove, force=options.force)
            td.write(options.delete)
        elif options.edit:
            td.edit_task(options.edit, text)
            td.write(options.delete)
        elif options.tag:
            td.tag(options.tag, text)
            td.write(options.delete)
        elif text:
            td.add_task(text, verbose=options.verbose, quiet=options.quiet, task_id=options.add, parent_id=options.sub)
            td.write(options.delete)
        else:
            kind = 'tasks' if not options.done else 'done'
            td.print_list(kind=kind, verbose=options.verbose, quiet=options.quiet,
                          grep=options.grep)
    except AmbiguousPrefix:
        e = sys.exc_info()[1]
        _die('the ID "%s" matches more than one task' % e.prefix)
    except UnknownPrefix:
        e = sys.exc_info()[1]
        _die('the ID "%s" does not match any task' % e.prefix)
    except BadFile as e:
        _die('%s - %s' % (e.problem, e.path))


if __name__ == '__main__':
    _main()
