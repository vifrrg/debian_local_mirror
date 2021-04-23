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

        self._fl_should = fl_list
        self._fl_current = None
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

    def _sort_temp_pass(self, fl_in, start=0, chunk=100):
        """
        Single pass of sort temporary file.
        :param fl_in: input file-like object
        :param start: start line for sorting
        :type start: int
        :param chunk: chunk size, in lines
        :type chunk: int
        :return: tuple (bool result, file-like fl_out)
        """
        _fl_out = NamedTemporaryFile(mode='w+')
        logging.info("Sort iteration: chunk = %d, start = %d" % (chunk, start))
        fl_in.seek(0, 0)

        _lines = list()
        _prev_lines = list()
        _result = True
        _catch_start = bool(start)
        _first_chunk = True

        while True:
            _line = fl_in.readline()

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
        fl_in.close()
        return _result, _fl_out

    def _sort_temp(self, fl):
        """
        Sorting a temporary file given
        :param fl: file-like temp object
        :return: sorted file-like object 
        """
        _result = False
        _start = 0
        _chunk = 55555
        #TODO: determine chunk size dynamically depending on memory available
        _fl_out = fl

        while not _result:
            _result, _fl_out = self._sort_temp_pass(fl_in=_fl_out, start=_start, chunk=_chunk)
            _start = 0 if _start else 33333
            _chunk = _start*2 if _start else 55555

        return _fl_out

    def remove_trash(self):
        """
        Remove files not found in our list
        """
        self._make_current_files_list()
        logging.info("Starting sorting legal files list...")
        self._fl_should = self._sort_temp(self._fl_should)
        logging.info("Starting sorting current files list...")
        self._fl_current = self._sort_temp(self._fl_current)

        #now we have two sorted files, starting comparison
        logging.debug("Starting lists comparison")
        self._fl_should.seek(0, 0)
        self._fl_current.seek(0, 0)

        _pth_legal = None
        _pth_current = None

        while True:
            if not _pth_legal:
                _pth_legal = self._fl_should.readline()

            if not _pth_current:
                _pth_current = self._fl_current.readline()

            if not _pth_legal and not _pth_current:
                logging.info("Trash cleanup finished")
                return

            if _pth_legal:
                _pth_legal = _pth_legal.strip()
            if _pth_current:
                _pth_current = _pth_current.strip()

            # check for empty line
            if not _pth_legal or not _pth_current:
                logging.warning("One of lines is empty, may be a sorting bug!")
                logging.warning("Legal: '%s'" % _pth_legal)
                logging.warning("Current: '%s'" % _pth_current)
                continue

            if _pth_legal == _pth_current:
                logging.debug("Equivalent found: '%s'" % _pth_legal)
                _pth_legal = None
                _pth_current = None
                continue

            if not os.path.exists(_pth_current):
                logging.warning("Path is in current list but does not exist. Bug?")
                logging.warning(_pth_current)
                _pth_current = None
                continue 

            logging.info("Removing obsolete '%s'" % _pth_current)
            os.remove(_pth_current)
            _pth_current = None

    def _make_current_files_list(self):
        """
        make current files list
        """
        _first_line = True
        logging.info("Making current files list...")
        self._fl_current = NamedTemporaryFile(mode='w+')
        self._fl_current.seek(0, 0)

        for _root, _dirs, _files in os.walk(self._src_dir):
            for _file in _files:
                _fullpth = os.path.join(_root, _file)
                logging.log(3, "Append current file: '%s'" % _fullpth)

                if not _first_line:
                    self._fl_current.write('\n')

                _first_line = False
                self._fl_current.write(_fullpth)

        self._fl_current.flush()
        logging.info("Current files list is ready")

    def get_temp(self):
        return self._fl_should

