#!/usr/bin/env python

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
import getopt
import logging
from keepassdb import LockingDatabase
try:
    import ConfigParser
except ImportError:
    from configparser import ConfigParser

logging.basicConfig()

class PkpCli(cmd.Cmd):
    """
    Pkpcli is a simple shell-like software to keepass DB files.
    It uses extensively the keepassdb module by Hans Lellelid
    (https://github.com/hozn/keepassdb)

    This class is a very simple wrapper for cmd.Cmd. Probably
    in the future this should be splitted into some other helper
    classes/modules.
    """
    def __init__(self, db_path=None, db_key=None):
        cmd.Cmd.__init__(self)

        self.db_path = db_path
        self.db_key = db_key
        self.db = None
        self.need_save = None

        self.intro = 'Simple KeePass db shell'
        self.ruler = '-'

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

            # is there a better way?
            p1,p2 = ('','.')
            while p1 != p2:
                p1 = getpass.getpass("Insert password for new DB %s: " % path)
                p2 = getpass.getpass('Repeat password: ')
            password = p1
            
        if key:
            raise NotImplementedError
            
        if not password:
            password = getpass.getpass("Insert DB password for %s: " % path)
            
        try:
            db = LockingDatabase(path, password=password, new=is_new)
            self.password = password
        except keepassdb.exc.DatabaseAlreadyLocked, e:
            print "The database is already in use or have a stale lock file"
            if self._confirm(message='Do you want to remove it (y/N)? ',
                             default=False):
                lock_file = "{}.lock".format(path)
                os.remove(lock_file)
                print "Lock %s removed" % lock_file
                print "Please re-launch this program"
                sys.exit(1)
            else:
                print 'Exiting...'
                sys.exit(0)
        except keepassdb.exc.AuthenticationError, e:
            print 'Hash sum mismatch: maybe wrong key/password?'
            return
        except Exception, e:
            print "Cannot open db %s: %s" % (path, e)
            lock_file = "{}.lock".format(path)
            os.remove(lock_file)
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
                if self._confirm(message="Database not saved! \nDo you want to save it now? (Y/n): ",default=True):
                    self.do_save()
            self.db.close()
        except Exception, e:
            print "Cannot close db %s: %s" % (self.db.filepath, e)
        finally:
            self.cwd = None
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

    def _current_childrens(self, what=None):
        """
        Returns a dict containing entries and group from
        self.cwd that can be used by all other functions 
        """
        d = dict()
        # orrible
        # convert into generators
        d_entries = {e.title: e for e in self.cwd.entries}
        d_groups = {g.title: g for g in self.cwd.children}
        if what == 'entries':
            return d_entries
        elif what == 'groups':
            return d_groups
        else:
            d['entries'] = d_entries
            d['groups'] = d_groups
            
        return d

    def _show_entry(self, complete=None, entry_name=None):
        '''
        Helper function to show an entry.
        Serves do_show() and do_showall()
        '''
        l = self._current_childrens('entries')            
        if entry_name in l.keys():
            e = l[entry_name]
        else:
            print 'Nothing to show...'
            return
        
        password = e.password if complete else '********'
        
        print '''
 {group}/{title}

 URL: {url}
 User: {username}
 Password: {password}
 Notes: {notes}
 Expires on: {expires}
 
 '''.format(title=e.title,
            group=e.group.title,
            username=e.username,
            url=e.url,
            password=password,
            notes=e.notes,
            expires=e.expires,
            )
        if complete:
            print '''
 Created: {created}
 Modified: {modified}
 Accessed: {accessed}
 --------------------
 '''.format(created=e.created,
            modified=e.modified,
            accessed=e.accessed)
        return

    def _confirm(self, message=None, default=False):
        '''
        Simple way to confirm question.
        Returns boolean
        '''
        a = raw_input(message)
        if a == '':
            return default
        if a in ['Y','y','yes','YES','Yes']:
            return True
        else:
            return False
        

    def _complete_entries(self, text, line, begidx, endidx):
        '''
        Still incomplete function to serve all completion
        '''
        return [e.title for e in self.cwd.entries if
                e.title.lower().startswith(text.lower())]

    def _complete_groups(self, text, line, begidx, endidx):
        '''
        Still incomplete function to serve all completion
        '''
        return [g.title for g in self.cwd.children if
                g.title.lower().startswith(text.lower())]

    def _attr_copy(self, what=None, entry_name=None):
        '''
        Copies username/password/other into clipboard
        '''
        try:
            import pyperclip
        except ImportError:
            print 'You need to install the pyperclip module to use this!'
            return

        l = self._current_childrens('entries')
        if entry_name in l.keys():
            e = l[entry_name]
        else:
            print 'No entry with that name!'
            return

        if not what in ['username', 'password', 'url']:
            raise NotImplementedError

        try:
            pyperclip.copy(getattr(e, what))
            print "%s copied into clipboard!" % what
        except Exception, e:
            print "Cannot copy %s into clipboard: %s" % (what, e)
            return

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
            return filter(lambda x: x.startswith(filename), ls)

    def do_open(self, line):
        """
        Opens a kdb file
        Usage: open FILENAME
        """
        self.db = self._open_db(path=line)
        return

    @db_opened
    def do_save(self, line=None):
        """
        Save an existing or new db
        Usage: save [FILENAME]
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
            self.db.save(dbfile=line, password=self.db.password)
            self.need_save = None
        except Exception, e:
            print "Cannot save db: %s" % e
            
        return

    @db_opened
    def do_close(self, line):
        """
        Close the current DB
        Usage: close
        """
        self._close_db()
        
        return

    @db_opened
    def do_ls(self, line):
        """
        List content of the current group
        Usage: ls
        """
        l = self._current_childrens()
        
        for key in l['groups']:
            print "\033[1;36m{}/\033[1;m".format(key)
            
        for key in l['entries']:
            print "{}".format(key)

        return

    @db_opened
    def do_cd(self, line):
        """
        Moves throught groups
        Usage: cd GROUP
        """
        if not line or line == '/': 
            self.cwd = self.db.root       
        elif line == '..':
            if self.cwd.title != '/':
                self.cwd = self.cwd.parent
        else:
            l = self._current_childrens('groups')
            if line in l.keys():
                self.cwd = l[line]
        return
    
    def do_find(self, line):
        """
        find entry
        """
        raise NotImplementedError

    @db_opened
    def do_pwd(self, line):
        """
        Prints full "path"
        Usage: pwd
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
        return
 
    @db_opened
    def do_show(self, line):
        """
        Shows an (incomplete) entry
        Usage: show ENTRY
        Alias: cat
        """
        if not line:
            return
        
        self._show_entry(complete=None,entry_name=line)
        
        return

    @db_opened
    def do_showall(self, line):
        """
        Show all entry
        Usage: showall ENTRY
        """
        if not line:
            return
        
        self._show_entry(complete=True,entry_name=line)
        
        return
    
    def do_cpu(self, line):
        """
        Copy username into clipboard
        Usage: cpu ENTRY
        """
        self._attr_copy(what='username',entry_name=line)
        return
    
    def do_cpp(self, line):
        """
        Copy password into clipboard
        Usage: cpp ENTRY
        """
        self._attr_copy(what='password',entry_name=line)
        return

    def do_cpurl(self, line):
        """
        Copy URL into clipboard
        Usage: cpurl ENTRY
        """
        self._attr_copy(what='url',entry_name=line)
        return
        
    def _external_edit(self, entry=None):
        """
        Manage all stuff related to temp file
        (read/write/create/delete)
        
        """
        tmpfile = tempfile.NamedTemporaryFile('w+b', delete=False)
        editor = os.environ.get('EDITOR') # use fallback

        # l = self._current_childrens('entries')
        # if entry_name in l.keys():
        #     e = l[entry_name]
        # else:
        #     # set an empty entry
        #     print 'Creating new entry!'
            

        template ='''
[entry]
Title = {title}
Url = {url}
User = {user}
Note = {notes}
'''

        # populate with values
        entry_template = template.format(title=entry.title,
                              url=entry.url,
                              user=entry.username,
                              notes=entry.notes
            )
        
        try:
            tmpfile.writelines(entry_template)
#            tmpfile.seek(0)
        except Exception, e:
            print 'Cannot write to %s: %s' % (tmpfile.name, e)
        finally:
            tmpfile.close()

        print os.path.exists(tmpfile.name)

        # edit entry with external editor
        if not subprocess.call("%s %s" % (editor, tmpfile.name), shell=True) == 0:
            print 'Editor did not exited correctly!'
            return

        c = ConfigParser.SafeConfigParser()
        c.read(tmpfile.name)
            
        entry.title = c.get('entry', 'Title')
        entry.group = self.cwd
        entry.url = c.get('entry', 'Url')
        entry.username = c.get('entry', 'User')
        entry.notes = c.get('entry', 'Note')
                
        print 'Entry saved!'

        # remove the temp file
        try:
            os.remove(tmpfile.name)
        except Exception, e:
            print 'Cannot remove file %s: %s' % (tmpfile.name, e)
            
        return entry

    @db_opened
    def do_new(self, line):
        """
        Creates new entry in the current directory
        Usage: new ENTRYNAME
        """
        
        l = self._current_childrens('entries')
        if line in l.keys():
            print 'Cannot create %s: already existing' % line
            print 'Try using \'edit\' instead...'
            return
        else:
            if self.cwd.title == '/':
                print 'Cannot create entry into the root group!'
                return
            try:
                _entry = self.db.create_entry(
                    group=self.cwd,
                    title=line,
                    url='Insert url',
                    username='Insert username',
                    notes='Insert notes',
                    )
            except Exception, e:
                 print 'Cannot create entry: %s' % e
            _entry = self._external_edit(entry=_entry)
            print 'Entry %s created' % _entry.title
            print 'To set password use \'passwd %s\'' % _entry.title
            self.need_save = True
            return

    @db_opened
    def do_edit(self, line):
        """
        Edit an existing entry
        Usage: edit ENTRYNAME
        """
        l = self._current_childrens('entries')
        if line in l.keys():
            _entry = l[line]
            self._external_edit(entry=_entry)
            self.need_save = True
            print '[INFO] to change an entry\'s password use \'passwd\''
        else:
            print 'Entry does not exists, creating new one...'
            self.do_new(line)
        return
        
    @db_opened
    def do_mkdir(self, line):
        """
        Creates new group
        Usage: mkdir GROUP
        """
        if not line:
            # is there a way to automatically do this?
            print 'Usage: mkdir GROUPNAME'
            return

        p = None if self.cwd.title == '/' else self.cwd
            
        self.db.create_group(parent=p,title=line)
        self.need_save = True

    def _generate_password(self, pw_len=8, special_chars=None):
        '''
        Code stolen!
        Simply return random password of given len
        '''
        import random

        alphabet = "abcdefghijklmnopqrstuvwxyz"
        special_c = '!@#$%^&*()'
        upperalphabet = alphabet.upper()
        pwlist = []

        for i in range(pw_len//3):
            pwlist.append(alphabet[random.randrange(len(alphabet))])
            pwlist.append(upperalphabet[random.randrange(len(upperalphabet))])
            if special_chars:
                pwlist.append(special_c[random.randrange(len(special_c))])
            pwlist.append(str(random.randrange(10)))
        for i in range(pw_len-len(pwlist)):
            pwlist.append(alphabet[random.randrange(len(alphabet))])
        random.shuffle(pwlist)
        pwstring = "".join(pwlist)
        return pwstring
        
    @db_opened
    def do_passwd(self, line):
        '''
        Sets password to entries
        Usage: passwd [-lNUM] [-s] ENTRY
            OPTIONS:
                -lNUM password lenght (NUM)
                -s    use special characters (default No)
        '''
        o,a = getopt.getopt(line.split(), 'l:s')
        
        opts = dict()

        pw_len = 8
        special_chars = False
        generate = False
        
        for k,v in o:
            opts[k] = v
        if opts.has_key('-l'):
            pw_len = int(opts['-l'])
            generate = True
            print '[INFO] Generating password of %s chars' % pw_len
        if opts.has_key('-s'):
            special_chars = True
            generate = True
            print '[INFO] Using special chars'

        l = self._current_childrens('entries')
        if a[0] in l.keys():
            _entry = l[a[0]]
        else:
            print 'Cannot find entry %s ' % a[0]
            return

        if generate:
            password = self._generate_password(pw_len=pw_len, special_chars=special_chars)
        else:
            p1 = getpass.getpass('Insert password for %s: ' % line)
            p2 = getpass.getpass('Repeat password: ')
            if p1 != p2:
                print 'Password mismatch!'
                return
            else:
                password = p1

        try:
            _entry.password = password
            print 'Password set successfully'
            self.do_save()
        except Exception, e:
            'Cannot set password for %s: %s' % (_entry.title, e)
            return
    
    @db_opened
    def do_rm(self, line):
        """
        Delete an entry
        Usage: rm ENTRY
        """
        if not line:
            print 'Usage: rm ENTRY'
            return

        e = self._current_childrens('entries')
        if not line in e.keys():
            print 'Entry %s not found!' % line
            return
        _entry = e[line]
        m = 'Do you want to remove \'%s\' (y/N)? ' % line
        if self._confirm(message=m, default=False):
            try:
                self.db.remove_entry(entry=_entry)
                print 'Entry \'%s\' removed' % line
                self.need_save = True
            except Exception, e:
                print 'Cannot remove entry %s: %s' % (line, e)
            finally:
                return
        else:
            return

    @db_opened
    def do_rmdir(self, line):
        """
        Delete a group
        Usage: rmdir GROUP
        """
        
        if not line:
            print 'Usage: rmgroup GROUPNAME'
            return

        g = self._current_childrens('groups')
        if not line in g.keys():
            print 'Group \'%s\' not found!' % line
            return
        _group = g[line]
        m = "Do you want to remove \'%s\' and all it's entries now (y/N)? " % line
        if self._confirm(message=m,default=False):            
            try:
                self.db.remove_group(group=_group)
                print 'Group \'%s\' removed!' % line
                self.need_save = True
            except Exception, e:
                print 'Cannot remove group %s: %s' % (line, e)
            finally:
                return
        else:
            return

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

    # some aliases
    complete_cat = _complete_entries
    complete_show = _complete_entries
    complete_showall = _complete_entries
    complete_cpu = _complete_entries
    complete_cpurl = _complete_entries
    complete_cpp = _complete_entries
    complete_edit = _complete_entries
    complete_passwd = _complete_entries
    complete_rm = _complete_entries
    complete_cd = _complete_groups
    complete_rmdir = _complete_groups
    do_cat = do_show

if __name__ == '__main__':

    parser = argparse.ArgumentParser(description="CLI interface to KeePass DB files")
    parser.add_argument('-d','--database',metavar='DBFILE',help='Database file')
    parser.add_argument('-k','--keyfile',metavar='KEYFILE',help='The keyfile to use')
    args = parser.parse_args()
    c = PkpCli(db_path=args.database, db_key=args.keyfile)
    try:
        c.cmdloop()
    except Exception, e:
        print 'Unexpected error!: %s' % e
    finally:
        c._close_db()
