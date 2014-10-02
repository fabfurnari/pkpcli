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
        keepassdb.model.RootGroup.title = '/'
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
        else:
            self.prompt = "{}> ".format(self.cwd.title)
        return

    def _build_struct(self, what=None):
        """
        Builds a dict containing entries and group from
        self.cwd that can be used by all other functions 
        """
        d = dict()
        # orrible
        if what == 'entries':
            d = dict([(e.title, e) for e in self.cwd.entries])
        elif what == 'groups':
            d = dict([(g.title, g) for g in self.cwd.children])
        else:
            d['entries'] = dict([(e.title, e) for e in self.cwd.entries])
            d['groups'] = dict([(g.title, g) for g in self.cwd.children])            
        return d

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
        l = self._build_struct()
        for key in l['groups']:
            print "\033[1;36m{}/\033[1;m".format(key)
        for key in l['entries']:
            print "{}".format(key)

    def complete_cd(self, text, line, begidx, endidx):
        """
        TODO: use _build_struct() instead
        """
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
            if self.cwd.title != '/':
                self.cwd = self.cwd.parent
        else:
            l = self._build_struct('groups')
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
            prompt_list.insert(0, group)
            if group.title == '/':
                return prompt_list
            else:
                return _pwd(group.parent)
        p = "/".join([x.title for x in _pwd(self.cwd)])
        print p

    def complete_show(self, text, line, begidx, endidx):
        return [e.title for e in self.cwd.entries if
                e.title.lower().startswith(text.lower())]
    
    @db_opened
    def do_show(self, line):
        """
        Show an entry
        TODO: mask password
        """
        if not line:
            return
        l = self._build_struct('entries')
        if line in l.keys():
            e = l[line]
            print '''
 {group}/{title}

 URL: {url}
 User: {username}
 Password: *******
            
 '''.format(title=e.title,
            group=e.group.title,
            username=e.username,
            url=e.url)

    def complete_showall(self, text, line, begidx, endidx):
        """
        TODO: find a way to merge with complete_show()
        """
        return [e.title for e in self.cwd.entries if
                e.title.lower().startswith(text.lower())]

    @db_opened
    def do_showall(self, line):
        """
        Show all entry
        """
        if not line:
            return
        l = self._build_struct('entries')
        if line in l.keys():
            e = l[line]
            print '''
 {group}/{title}

 URL: {url}
 User: {username}
 Password: {password}
 Notes: {notes}
 Expires on: {expires}

 Created: {created}
 Modified: {modified}
 Accessed: {accessed}
            
 '''.format(title=e.title,
            group=e.group.title,
            username=e.username,
            url=e.url,
            password=e.password,
            notes=e.notes,
            expires=e.expires,
            created=e.created,
            modified=e.modified,
            accessed=e.accessed,
     )

    def complete_cpu(self, text, line, begidx, endidx):
        """
        TODO: find a way to merge with complete_show()
        """
        return [e.title for e in self.cwd.entries if
                e.title.lower().startswith(text.lower())]            

    def do_cpu(self, line):
        """
        Copy username into the clipboard
        """
        raise NotImplementedError
    
    def do_cpp(self, line):
        """
        Copy password into the clipboard
        """
    def do_edit(self, line):
        """
        Edit an existing entry
        """
        raise NotImplementedError

    def do_new(self, line):
        """
        Creates new entry
        """
        raise NotImplementedError

    def do_mkdir(self, line):
        """
        Creates new group
        """
        raise NotImplementedError

    def do_rm(self, line):
        """
        Delete an entry
        """
        raise NotImplementedError

    def do_rmgroup(self, line):
        """
        Delete a group
        """
        raise NotImplementedError
        
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

    def default(self, line):
        cmd, arg, line = self.parseline(line)
        func = [getattr(self, n) for n in self.get_names() if n.startswith('do_' + cmd)]
        if func:
            func[0](arg)

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
