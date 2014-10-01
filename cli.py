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
        self.prompt = '>> '
        self.intro = 'Simple KeePass db shell'
        self.ruler = '-'

        self.db_path = db_path
        self.db_key = db_key
        self.db = None
        
        if self.db_path:
            # TODO: key file
            self.db = self._open_db(db_path,db_key)

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
        self.current_wd = db.root
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
        except Exception, e:
            print "Cannot close db %s: %s" % (self.db.filepath, e)
        finally:
            self.db = None

    def _print_group(self, group, level=0):
        """
        Shamelessly copied from official doc
        """
        level = 1
        indent = " " * level
        print '%s%s' % (indent, group.title)
        for entry in group.entries:
            print '%s -%s' % (indent, entry.title)
        for child in group.children:
            self._print_group(child, level+1)

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
    def do_ls(self, line=None):
        """
        List content of the current group
        """
        if not line:
            line = self.current_wd
        
        self._print_group(line)
        
    def do_cd(self, line):
        """
        Moves throught groups
        """
        raise NotImplementedError
    
    def do_find(self, line):
        """
        find entry
        """
        raise NotImplementedError

    def do_pwd(self, line):
        """
        Prints full "path"
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
        self._close_db
        return True

    def emptyline(self):
        """
        To avoid the repeat-last-command behavior
        """
        pass
        

if __name__ == '__main__':

    parser = argparse.ArgumentParser(description="CLI interface to KeePass DB files")
    parser.add_argument('-d','--database',metavar='DBFILE',help='Database file')
    parser.add_argument('-k','--keyfile',metavar='KEYFILE',help='The keyfile to use')
    args = parser.parse_args()

    c = PkpCli(db_path=args.database, db_key=args.keyfile)

    try: # Just for debug
        c.cmdloop()
    finally:
        c._close_db()
