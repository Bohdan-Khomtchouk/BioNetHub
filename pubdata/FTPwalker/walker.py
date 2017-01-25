"""
=====
walker.py
=====

Traverse the FTP servers with BFS algorithm.

============================

"""

from os import path as ospath


class ftp_walker(object):
    """
    ==============

    ``ftp_walker``
    ----------

    .. py:class:: ftp_walker()

    This class is contain corresponding functions for traversing the FTP
    servers using BFS algorithm.

    """
    def __init__(self, connection, resume=False):
        """
        .. py:attribute:: __init__()


           :param connection: FTP connection object
           :type connection: ftplib.connection
           :rtype: None

        """
        self.connection = connection
        self.resume = resume

    def listdir(self, _path):
        """
        .. py:attribute:: listdir()

        return files and directory names within a path (directory)
           :param _path: path of a directory
           :type _path: str
           :rtype: tuple

        """
        file_list, dirs, nondirs = [], [], []
        try:
            self.connection.cwd(_path)
        except Exception as exp:
            print ("the current path is : ", self.connection.pwd(), exp.__str__(), _path)
            return [], []
        else:
            self.connection.retrlines('LIST', lambda x: file_list.append(x.split()))
            for info in file_list:
                ls_type, name = info[0], info[-1]
                if ls_type.startswith('d'):
                    dirs.append(name)
                else:
                    nondirs.append(name)
            return dirs, nondirs

    def walk_resume(self, root, paths):
        for items in self.walk(root):
            yield items
        parent = ospath.dirname(root)

        def find_diff(parent):
            dirs, _ = self.listdir(parent)
            diffs = set(paths).difference(dirs)
            for name in diffs:
                yield from self.walk(name)
        find_diff(parent)
        if parent != '/':
            parent = ospath.dirname(root)
            yield from find_diff(parent)

    def walk(self, path='/'):
        """
        .. py:attribute:: Walk()

        Walk through FTP server's directory tree
           :param path: Leading path
           :type path: str
           :rtype: generator (path and files)

        """
        dirs, nondirs = self.listdir(path)
        yield path, dirs, nondirs
        print ((path, dirs))
        for name in dirs:
            path = ospath.join(path, name)
            yield from self.Walk(path)
            self.connection.cwd('..')
            path = ospath.dirname(path)