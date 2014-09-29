"""
Simple cmd interface
"""

import cmd

class PkpCli(cmd.Cmd):
    """
    TODO
    """

    def do_ls(self, line):
        """
        List content of the current group
        """
        raise NotImplementedError

    def do_EOF(self, line):
        """
        Exits
        """
        return True

if __name__ == '__main__':
    PkpCli().cmdloop()
