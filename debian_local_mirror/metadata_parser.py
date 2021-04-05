import logging

class FormatError(Exception):
    def __init__(self, path, message):
        super().__init__('%s: Format error: %s' % (path, message))

class DebianMetaParser(object):
    _sep = ":" # value-key separator
    _list_feilds = [] # keys for which value should be a list
    _list_sep = " " # separator for list-fields

    def _convert_list_field(self, key, value):
        """
        Smartly convert a key-value pair to list
        if specified in the fld.
        :param key: key
        :type key: str
        :param value: the value
        :type value: str
        :return: value modified
        """
        if key not in self._list_fields:
            return value

        if not value or not isinstance(value, str):
            return value

        return list(value.split(self._list_sep))

    def _append_result(self, result, key, value):
        """
        Smartly append key-value pair to the result
        :param result: where to append
        :type result: dict, list
        :param key: key
        :type key: str
        :param value: value
        :type value: str, list[str], dict
        :return: modified result
        """
        value = self._convert_list_field(key, value)

        if isinstance(result, dict):
            result[key] = value
            return result
        
        if isinstance(result, list):
            result[-1][key] = value
            return result
        
        raise TypeError("Result is not a list and not a dict, this is unexpected")

    def parse(self):
        """
        Try to parse debian metadata file to dictionary
        """

        if not (self._fd):
            raise ValueError("File descriptor not given")

        self._fd.seek(0,0)

        _result = dict()
        logging.debug("Parse: result is %s" % type(_result))

        # file is considered as opened in text mode
        # but if it is binary - we cosider as "utf"-encoded

        _key = ""
        _value = ""
        _append_new_dict = False

        while True:
            _ln = self._fd.readline()

            if _key and _append_new_dict:
                _result.append(dict())
                _append_new_dict = False

            if not _ln:
                # append last value to a dict
                logging.debug("End of file reached")
                _result = self._append_result(_result, _key, _value)
                break

            _ln = _ln.strip()

            if not len(_ln):
                if not _key:
                    logging.debug("Unexpeced empty line in '%s'" % self._local)
                    continue

                _result = self._append_result(_result, _key, _value)

                if isinstance(_result, dict):
                    logging.debug("Converting result to list")
                    _result = [_result]
                    _append_new_dict = True

                _key = ""
                _value = ""
                continue

            if self._sep not in _ln:
                if not _key:
                    raise FormatError(self._local, "Value without a key found")

                # this is a list value
                if not isinstance(_value, list):
                    if _value:
                        _value = [_value]
                    else:
                        _value = list()

                _value.append(_ln)

                continue

            if _key:
                if not _value:
                    raise FormatError(self._local, "Key '%s' without value" % _key)

                self._append_result(_result, _key, _value)

            _key, _value = _ln.split(":", 1)
            _key = _key.strip()
            _value = _value.strip()
            logging.debug("Got pair: '%s' = '%s'" % (_key, _value))

        return _result

