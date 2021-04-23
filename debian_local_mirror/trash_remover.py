#!/usr/bin/python3

from tempfile import NamedTemporaryFile
import os
import logging
from copy import deepcopy
import shutil

class TrashRemover(object):
    """
    Special processing of temporary files
    """

    def __init__(self, fl_list, src_dir):
        """
        Initailization
        :param fl_list: temporary file list
        :type fl_list: file-like object open in read text mode
        :param src_dir: source directory to search files in
        :type src_dir: str
        """

        self._fl_list = fl_list
        self._src_dir = os.path.abspath(src_dir)

    def _sort_compare_lines(self, lines, fl_out=None, compare=False, first_chunk=False):
        """
        Sort and put out lines
        By-condition comparison of sorted list with non-sorted.
        :param lines: lines to sort
        :type lines: list of str
        :param fl_out: file-like object to put sorted lines to
        :param compare: do comparison
        :type compare: bool
        :param first_chunk: Process it as first chunk or not. First chunk does not add newline before it
        :type first_chunk: boolean
        :return: result of comparison or False if comparison is skipped
        """
        _result = compare

        if _result:
            _prev_lines = deepcopy(lines)
        
        lines.sort()

        if not first_chunk:
            fl_out.write('\n')

        fl_out.write('\n'.join(lines))
        fl_out.flush()
                
        if _result and lines != _prev_lines:
            logging.info("Result will be false since lines differ")
            _result = False

        return _result

    def _sort_temp(self, start=0, chunk=100):
        """
        Single pass of sort temporary file.
        :param start: start line for sorting
        :type start: int
        :param chunk: chunk size, in lines
        :type chunk: int
        """
        _fl_out = NamedTemporaryFile(mode='w+')
        logging.info("Sort iteration: chunk = %d, start = %d" % (chunk, start))
        self._fl_list.seek(0, 0)

        _lines = list()
        _prev_lines = list()
        _result = True
        _catch_start = bool(start)
        _first_chunk = True

        while True:
            _line = self._fl_list.readline()

            if not _line:
                logging.info("End of file, sorting last chunk")
                _result = self._sort_compare_lines(
                    lines=_lines, 
                    fl_out=_fl_out,
                    compare=_result,
                    first_chunk=_first_chunk)
                _first_chunk = False
                break

            _line = _line.strip()

            if not _line:
                logging.debug("Empty line")
                continue

            if _line not in _lines:
                _lines.append(_line)
            elif _result:
                logging.info("Duplicate line found, result will be False")
                _result = False

            if len(_lines) >= chunk \
                    or (_catch_start and len(_lines) == start):
                _catch_start = False
                logging.info("Sorting next chunk")
                _result = self._sort_compare_lines(
                    lines=_lines, 
                    fl_out=_fl_out,
                    compare=_result,
                    first_chunk=_first_chunk)
                _first_chunk = False
                _lines = list()

        _fl_out.flush()
        self._fl_list.close()
        self._fl_list = _fl_out
        return _result

    def sort_temp(self):
        """
        Sorting a temporary file given
        """
        _result = False
        _start = 0
        _chunk = 55555

        while not _result:
            _result = self._sort_temp(_start, _chunk)
            _start = 0 if _start else 33333
            _chunk = _start*2 if _start else 55555

    def _is_in_files_list(self, path):
        """
        Check if a path was synchronized during the session
        :param path: path to check
        :type path: str
        """
        logging.log(3, "Searching '%s' in files list..." % path)

        self._fl_list.seek(0, 0)
        _fl_out = NamedTemporaryFile(mode='w+')
        _result = False
        _first_line = True

        while True:
            _line = self._fl_list.readline()

            if not _line:
                logging.log(3, "End of file")
                break

            _line = _line.strip()

            if not _line:
                logging.log(3, "Empty line")
                continue

            logging.log(3, "Comparison: '%s' <==> '%s'" % (path, _line))

            if _line == path:
                logging.log(3, "Returning True")
                _result = True
                break

            if not _first_line:
                _fl_out.write('\n')

            _first_line = False
            _fl_out.write(_line)

        if _result:
            if not _first_line:
                _fl_out.write('\n')

            shutil.copyfileobj(self._fl_list, _fl_out)

        _fl_out.flush()
        self._fl_list.close()
        self._fl_list = _fl_out

        return _result


    def remove_trash(self):
        """
        Remove files not found in our list
        """
        for _root, _dirs, _files in os.walk(self._src_dir):
            for _file in _files:
                _fullpth = os.path.join(_root, _file)

                if not self._is_in_files_list(_fullpth):
                    logging.info("Removing obsolete '%s'" % _fullpth)
                    os.remove(_fullpth)

    def get_temp(self):
        return self._fl_list

