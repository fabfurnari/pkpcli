"""
Simple cmd interface
"""

import cmd
import argparse
import dircache
import getpass
import sys
import os
from functools import wraps
import keepassdb
from keepassdb import LockingDatabase
        
class PkpCli(cmd.Cmd):
    """
    TODO
    """
    def __init__(self, db_path=None, db_key=None):
        cmd.Cmd.__init__(self)
        self.intro = 'Simple KeePass db shell'
        self.ruler = '-'

        self.db_path = db_path
        self.db_key = db_key
        self.db = None
        
        if self.db_path:
            # TODO: key file
            self.db = self._open_db(db_path,db_key)
        self._set_prompt()

    def db_opened(f):
        """
        Very simple decorator to check if the
        DB is already opened
        """
        @wraps(f)
        def wrapper(self, *args, **kwargs):
            if self.db:
                return f(self, *args, **kwargs)
            else:
                print "Database file not opened!"
                return False
        return wrapper

    def _open_db(self, path, key=None, password=None):
        """
        Returns db object
        """
        if self.db:
            print "DB already opened!"
            print "Please close it first"
            return self.db
        if key:
            raise NotImplementedError
        if not password:
            password = getpass.getpass("Insert DB password: ")
        try:
            db = LockingDatabase(path, password=password)
        except keepassdb.exc.DatabaseAlreadyLocked, e:
            print "The database is already in use or have a stale lock file"
            print "Press Y to remove it or any other key to exit in this state"
            a = raw_input()
            if a == 'Y':
                lock_file = "{}.lock".format(path)
                os.remove(lock_file)
                print "Lock %s removed" % lock_file
                print "Please re-launch this program"
                sys.exit(1)
        except Exception, e:
            print "Cannot open db %s: %s" % (path, e)
            sys.exit(1)
                
        print "Working with DB file %s " % path
        self.cwd = db.root
        return db

    def _close_db(self):
        """
        Helper function to close the DB
        TODO: check if saved
        """
        if not self.db:
            return
        try:
            print "Closing db %s" % self.db.filepath
            self.db.close()
            self.cwd = None
        except Exception, e:
            print "Cannot close db %s: %s" % (self.db.filepath, e)
        finally:
            self.db = None

    def _set_prompt(self):
        """
        Simply set the prompt using the cwd
        Or sets a standard prompt if db not opened
        """
        if not self.db:
            self.prompt = '>> '
            return
        if self.cwd.title == 'Root Group':
            self.prompt = "/> "
        else:
            self.prompt = "{}> ".format(self.cwd.title)
        return

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
        self.db = self._open_db(path=line)

    @db_opened
    def do_save(self, line):
        """
        Save a new (or existing) db
        """
        try:
            self.db.save()
        except Exception, e:
            print "Cannot save db: %s" % e

    @db_opened
    def do_close(self, line):
        """
        Close the current DB
        TODO: warns if not saved 
        """
        self._close_db()

    @db_opened
    def do_ls(self, line):
        """
        List content of the current group
        Shamelessly copied from official doc
        TODO: list not only cwd
        """
        group = self.cwd
        #print " + {}".format(group.title)
        for child in group.children:
            print " {}/".format(child.title)
        for entry in group.entries:
            print " {}".format(entry.title)

    def complete_cd(self, text, line, begidx, endidx):
        return [g.title for g in self.cwd.children if
                g.title.lower().startswith(text.lower())]

    @db_opened
    def do_cd(self, line):
        """
        Moves throught groups
        """
        if not line or line == '/': 
            self.cwd = self.db.root
        elif line == '..':
            if self.cwd.title != 'Root Group':
                self.cwd = self.cwd.parent
        else:    
            l = dict([(e.title, e) for e in self.cwd.children])
            if line in l.keys():
                self.cwd = l[line]
    
    def do_find(self, line):
        """
        find entry
        """
        raise NotImplementedError

    @db_opened
    def do_pwd(self, line):
        """
        Prints full "path"
        """
        prompt_list = []
        def _pwd(group):
            prompt_list.insert(0,group)
            if group.title == 'Root Group':
                return prompt_list
            else:
                return _pwd(group.parent)
        p = "/".join([x.title for x in _pwd(self.cwd)])
        print p

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
        self._close_db
        return True

    def emptyline(self):
        """
        To avoid the repeat-last-command behavior
        """
        pass

    def postcmd(self, stop, line):
        """
        Override to simplify the prompt string creation
        """
        self._set_prompt()
        return cmd.Cmd.postcmd(self, stop, line)

if __name__ == '__main__':

    parser = argparse.ArgumentParser(description="CLI interface to KeePass DB files")
    parser.add_argument('-d','--database',metavar='DBFILE',help='Database file')
    parser.add_argument('-k','--keyfile',metavar='KEYFILE',help='The keyfile to use')
    args = parser.parse_args()

    c = PkpCli(db_path=args.database, db_key=args.keyfile)
    try:
        c.cmdloop()
    finally:
        c._close_db()
