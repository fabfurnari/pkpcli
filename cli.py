#!/usr/bin/env python
"""
Simple cmd interface
"""

import cmd
import argparse
import dircache
import getpass
import sys
import os
import tempfile
import subprocess
from functools import wraps
import keepassdb
from keepassdb import LockingDatabase

class PkpCli(cmd.Cmd):
    """
    
    """
    def __init__(self, db_path=None, db_key=None):
        cmd.Cmd.__init__(self)
        self.intro = 'Simple KeePass db shell'
        self.ruler = '-'

        self.db_path = db_path
        self.db_key = db_key
        self.db = None
        self.need_save = None
        
        if self.db_path:
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
        if os.path.isfile(path):
            is_new = None
        else:
            print 'Creating new KeePass DB: %s' % path
            is_new = True
            self.need_save = True
        if key:
            raise NotImplementedError
        if not password:
            password = getpass.getpass("Insert DB password: ")
        try:
            db = LockingDatabase(path, password=password, new=is_new)
            self.password = password
        except keepassdb.exc.DatabaseAlreadyLocked, e:
            print "The database is already in use or have a stale lock file"
            a = raw_input("Press Y to remove it or any other key to exit in this state: ")
            if a == 'Y':
                lock_file = "{}.lock".format(path)
                os.remove(lock_file)
                print "Lock %s removed" % lock_file
                print "Please re-launch this program"
                sys.exit(1)
        except Exception, e:
            print "Cannot open db %s: %s" % (path, e)
            sys.exit(1)
            
        if is_new:
            print 'Creating default groups...'
            db.create_default_group()
            
        print "Working with DB file %s " % path
        self.cwd = db.root
        return db

    def _close_db(self):
        """
        Helper function to close the DB
        """
        if not self.db:
            return
        try:
            print "Closing db %s" % self.db.filepath
            if self.need_save:
                print
                a = raw_input('Database not saved, do you want to save it now? (Y/n): ')
                if a in ['Y','y','yes','Yes','YES','']:
                    self.do_save()
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
        """
        self.db = self._open_db(path=line)

    @db_opened
    def do_save(self, line=None):
        """
        Save a new (or existing) db
        """
        if line == '': line = None # horrible
        try:
            if not self.db.groups:
                print 'Cannot save empty group!'
                print 'Creating the default one...'
                self.db.create_default_group()
        except Exception, e:
            print "Cannot create defaut groups to db: %s" % e
        try:
            self.db.save(dbfile=line, password=self.password)
            self.need_save = None
        except Exception, e:
            print "Cannot save db: %s" % e

    @db_opened
    def do_close(self, line):
        """
        Close the current DB
        """
        self._close_db()

    @db_opened
    def do_ls(self, line):
        """
        List content of the current group
        Shamelessly copied from official doc
        """
        l = self._build_struct()
        for key in l['groups']:
            print "\033[1;36m{}/\033[1;m".format(key)
        for key in l['entries']:
            print "{}".format(key)

    def complete_cd(self, text, line, begidx, endidx):
        """
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
        Shows an (incomplete) entry
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

    def _external_edit(entry=None):
        """
        Manage all stuff related to temp file
        (read/write/create/delete)
        
        """
        tmpfile = tempfile.mkstemp()[1]
        editor = os.environment.get('EDITOR') # use fallback

        if entry:
            # parse all entry data here/put into dict
            # see if keepassdb already has db
            pass
        else:
            # set an empty entry
            entry = dict()
            # Set all values to default
            pass
        
        entry_template = '''
        Title = {title}
        Url = {url}
        User = {user}
        And so on...
        '''

        # populate with values
        entry_template.format(title=entry['title'],
                              url=entry['url'],
                              # and so on
            )
        with open(tmpfile) as f:
            f.write(entry_template)
            f.close()

        # edit entry with external editor
        if subprocess.call("%s %s" % (editor, tmpfile)) == 0:
            # parse the file and put values into dict
            # maybe use an ini file helper library
            pass
        else:
            # editor does not exited correctly
            pass

        # remove the temp file
        os.remove(tmpfile)
        return entry

        raise NotImplementedError
    
    def do_edit(self, line):
        """
        Edit an existing entry
        Usage: edit ENTRYNAME

        TODO: 1. Read entry values (not password)
              2. Write entry into file (use template)
              3. set editor and so on
              4. open temp file with editor
              ...user edits and saves file...
              5. read temp file / parse fields
              6. write entry
              7. ask user if wants to change password
              8. change password
              8. save entry
              9. delete temp file
        """
        raise NotImplementedError

    @db_opened
    def do_new(self, line):
        """
        Creates new entry in the current directory
        Usage: new ENTRYNAME

        TODO: 1. create temp file
              2. write template into file
              3. set editor, and so on
              4. open the temp file with editor
              ...user edits and saves file...
              5. read temp file / parse fields
              6. ask user for password / set password
              7. save entry
              8. delete temp file
        """
        tmpfile = tempfile.mkstemp()[1]
        editor = os.environ.get('EDITOR')
        subprocess.call('{0} {1}'.format(editor, tmpfile), shell=True)
        return NotImplementedError

    @db_opened
    def do_mkdir(self, line):
        """
        Creates new group
        Usage: mkdir GROUPNAME
        """
        if not line:
            # is there a way to automatically do this?
            print 'Usage: mkdir GROUPNAME'
            return

        p = None if self.cwd.title == '/' else self.cwd
            
        self.db.create_group(parent=p,title=line)
        self.need_save = True

    def do_rm(self, line):
        """
        Delete an entry
        """
        raise NotImplementedError

    def complete_rmdir(self, text, line, begidx, endidx):
        """
        """
        return [g.title for g in self.cwd.children if
                g.title.lower().startswith(text.lower())]

    @db_opened
    def do_rmdir(self, line):
        """
        Delete a group
        TODO: delete multiple groups
        """
        
        if not line:
            print 'Usage: rmgroup GROUPNAME'
            return

        group = [_g for _g in self.db.groups if _g.title == line][0]
        
        self.db.remove_group(group=group)
        self.need_save = True

        
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

        self.do_cat = self.do_show

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
