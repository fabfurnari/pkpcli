"""
Simple cmd interface
"""

import cmd
import dircache
import getpass
from keepassdb import Database
        
class PkpCli(cmd.Cmd):
    """
    TODO
    """
    def __init__(self):
        cmd.Cmd.__init__(self)
        self.prompt = '>> '
        self.intro = 'Simple KeePass db shell'
        self.ruler = '-'

    def complete_open(self, text, line, begidx, endidx):
        """
        auto complete of file name.
        """
        line = line.split()
        if len(line) < 2:
            filename = ''
            path = './'
        else:
            path = line[1]
            if '/' in path:
                i = path.rfind('/')
                filename = path[i+1:]
                path = path[:i]
            else:
                filename = path
                path = './'

        ls = dircache.listdir(path)
        ls = ls[:] # for overwrite in annotate.
        dircache.annotate(path, ls)
        if filename == '':
            return ls
        else:
            return [f for f in ls if f.startswith(filename)]

    def do_open(self, line):
        """
        Opens a kbd file
        NOTE: encrypt memory (if possible)
        TODO: Autocomplete should work....
        """
        p = getpass.getpass(prompt="Insert file password: ")
        db = Database(line, password=p)
        self.db_opened = True # to check
        print "Database % opened" % line
        
    def do_save(self, line):
        """
        Save a new (or existing) kbd file
        """
        raise NotImplementedError

    def do_close(self, line):
        """
        Close a kbd file
        NOTE: warns if not saved 
        """
        raise NotImplementedError

    def do_ls(self, line):
        """
        List content of the current group
        """
        raise NotImplementedError

    def do_show(self, line):
        """
        Show an entry
        """
        raise NotImplementedError

    def do_cpu(self, line):
        """
        Copy username into the clipboard
        """
        raise NotImplementedError

    def do_cpp(self, line):
        """
        Copy password into the clipboard
        """

    def do_EOF(self, line):
        """
        Exits
        """
        return True

if __name__ == '__main__':
    PkpCli().cmdloop()
