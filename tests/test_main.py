# -*- coding: utf-8 -*-


from wakatime.main import execute
from wakatime.packages import requests

import logging
import os
import time
import re
import shutil
import sys
from testfixtures import log_capture
from wakatime.compat import u, is_py3
from wakatime.constants import (
    API_ERROR,
    AUTH_ERROR,
    CONFIG_FILE_PARSE_ERROR,
    SUCCESS,
    MALFORMED_HEARTBEAT_ERROR,
)
from wakatime.packages.requests.exceptions import RequestException
from wakatime.packages.requests.models import Response
from . import utils

try:
    from .packages import simplejson as json
except (ImportError, SyntaxError):
    import json
try:
    from mock import ANY, call
except ImportError:
    from unittest.mock import ANY, call
from wakatime.packages import tzlocal


class MainTestCase(utils.TestCase):
    patch_these = [
        'wakatime.packages.requests.adapters.HTTPAdapter.send',
        'wakatime.offlinequeue.Queue.push',
        ['wakatime.offlinequeue.Queue.pop', None],
        ['wakatime.offlinequeue.Queue.connect', None],
        'wakatime.session_cache.SessionCache.save',
        'wakatime.session_cache.SessionCache.delete',
        ['wakatime.session_cache.SessionCache.get', requests.session],
        ['wakatime.session_cache.SessionCache.connect', None],
    ]

    def test_help_contents(self):
        args = ['--help']
        with self.assertRaises(SystemExit) as e:
            execute(args)

        self.assertEquals(int(str(e.exception)), 0)
        expected_stdout = open('tests/samples/output/test_help_contents').read()
        self.assertEquals(sys.stdout.getvalue(), expected_stdout)
        self.assertEquals(sys.stderr.getvalue(), '')

        self.patched['wakatime.offlinequeue.Queue.push'].assert_not_called()
        self.patched['wakatime.offlinequeue.Queue.pop'].assert_not_called()

    def test_argument_parsing(self):
        response = Response()
        response.status_code = 201
        self.patched['wakatime.packages.requests.adapters.HTTPAdapter.send'].return_value = response

        with utils.TemporaryDirectory() as tempdir:
            entity = 'tests/samples/codefiles/twolinefile.txt'
            shutil.copy(entity, os.path.join(tempdir, 'twolinefile.txt'))
            entity = os.path.realpath(os.path.join(tempdir, 'twolinefile.txt'))

            config = 'tests/samples/configs/good_config.cfg'
            args = ['--file', entity, '--key', '123', '--config', config]

            retval = execute(args)
            self.assertEquals(retval, SUCCESS)
            self.assertEquals(sys.stdout.getvalue(), '')
            self.assertEquals(sys.stderr.getvalue(), '')

            self.patched['wakatime.session_cache.SessionCache.get'].assert_called_once_with()
            self.patched['wakatime.session_cache.SessionCache.delete'].assert_not_called()
            self.patched['wakatime.session_cache.SessionCache.save'].assert_called_once_with(ANY)

            self.patched['wakatime.offlinequeue.Queue.push'].assert_not_called()
            self.patched['wakatime.offlinequeue.Queue.pop'].assert_called_once_with()

    def test_config_file_not_passed_in_command_line_args(self):
        response = Response()
        response.status_code = 201
        self.patched['wakatime.packages.requests.adapters.HTTPAdapter.send'].return_value = response

        with utils.TemporaryDirectory() as tempdir:
            entity = 'tests/samples/codefiles/emptyfile.txt'
            shutil.copy(entity, os.path.join(tempdir, 'emptyfile.txt'))
            entity = os.path.realpath(os.path.join(tempdir, 'emptyfile.txt'))

            with utils.mock.patch('wakatime.main.open') as mock_open:
                mock_open.side_effect = IOError('')

                config = os.path.join(os.path.expanduser('~'), '.wakatime.cfg')
                args = ['--file', entity]

                with self.assertRaises(SystemExit) as e:
                    execute(args)

                self.assertEquals(int(str(e.exception)), CONFIG_FILE_PARSE_ERROR)
                expected_stdout = u('')
                expected_stderr = u("Error: Could not read from config file {0}\n").format(u(config))
                self.assertEquals(sys.stdout.getvalue(), expected_stdout)
                self.assertEquals(sys.stderr.getvalue(), expected_stderr)
                self.patched['wakatime.session_cache.SessionCache.get'].assert_not_called()

    def test_missing_config_file(self):
        config = 'foo'

        with utils.TemporaryDirectory() as tempdir:
            entity = 'tests/samples/codefiles/emptyfile.txt'
            shutil.copy(entity, os.path.join(tempdir, 'emptyfile.txt'))
            entity = os.path.realpath(os.path.join(tempdir, 'emptyfile.txt'))

            args = ['--file', entity, '--config', config]
            with self.assertRaises(SystemExit) as e:
                execute(args)

            self.assertEquals(int(str(e.exception)), CONFIG_FILE_PARSE_ERROR)
            expected_stdout = u('')
            expected_stderr = u("Error: Could not read from config file foo\n")
            self.assertEquals(sys.stdout.getvalue(), expected_stdout)
            self.assertEquals(sys.stderr.getvalue(), expected_stderr)

            self.patched['wakatime.session_cache.SessionCache.get'].assert_not_called()

    def test_good_config_file(self):
        response = Response()
        response.status_code = 201
        self.patched['wakatime.packages.requests.adapters.HTTPAdapter.send'].return_value = response

        with utils.TemporaryDirectory() as tempdir:
            entity = 'tests/samples/codefiles/emptyfile.txt'
            shutil.copy(entity, os.path.join(tempdir, 'emptyfile.txt'))
            entity = os.path.realpath(os.path.join(tempdir, 'emptyfile.txt'))

            config = 'tests/samples/configs/has_everything.cfg'
            args = ['--file', entity, '--config', config]
            retval = execute(args)
            self.assertEquals(retval, SUCCESS)
            expected_stdout = open('tests/samples/output/main_test_good_config_file').read()
            traceback_file = os.path.realpath('wakatime/main.py')
            lineno = int(re.search(r' line (\d+),', sys.stdout.getvalue()).group(1))
            self.assertEquals(sys.stdout.getvalue(), expected_stdout.format(file=traceback_file, lineno=lineno))
            self.assertEquals(sys.stderr.getvalue(), '')

            self.patched['wakatime.session_cache.SessionCache.get'].assert_called_once_with()
            self.patched['wakatime.session_cache.SessionCache.delete'].assert_not_called()
            self.patched['wakatime.session_cache.SessionCache.save'].assert_called_once_with(ANY)

            self.patched['wakatime.offlinequeue.Queue.push'].assert_not_called()
            self.patched['wakatime.offlinequeue.Queue.pop'].assert_called_once_with()

    def test_api_key_without_underscore_accepted(self):
        response = Response()
        response.status_code = 201
        self.patched['wakatime.packages.requests.adapters.HTTPAdapter.send'].return_value = response

        with utils.TemporaryDirectory() as tempdir:
            entity = 'tests/samples/codefiles/emptyfile.txt'
            shutil.copy(entity, os.path.join(tempdir, 'emptyfile.txt'))
            entity = os.path.realpath(os.path.join(tempdir, 'emptyfile.txt'))

            config = 'tests/samples/configs/sample_alternate_apikey.cfg'
            args = ['--file', entity, '--config', config]
            retval = execute(args)
            self.assertEquals(retval, SUCCESS)
            self.assertEquals(sys.stdout.getvalue(), '')
            self.assertEquals(sys.stderr.getvalue(), '')

            self.patched['wakatime.session_cache.SessionCache.get'].assert_called_once_with()
            self.patched['wakatime.session_cache.SessionCache.delete'].assert_not_called()
            self.patched['wakatime.session_cache.SessionCache.save'].assert_called_once_with(ANY)

            self.patched['wakatime.offlinequeue.Queue.push'].assert_not_called()
            self.patched['wakatime.offlinequeue.Queue.pop'].assert_called_once_with()

    def test_bad_config_file(self):
        with utils.TemporaryDirectory() as tempdir:
            entity = 'tests/samples/codefiles/emptyfile.txt'
            shutil.copy(entity, os.path.join(tempdir, 'emptyfile.txt'))
            entity = os.path.realpath(os.path.join(tempdir, 'emptyfile.txt'))

            config = 'tests/samples/configs/bad_config.cfg'
            args = ['--file', entity, '--config', config]
            retval = execute(args)
            self.assertEquals(retval, CONFIG_FILE_PARSE_ERROR)
            self.assertIn('ParsingError', sys.stdout.getvalue())
            self.assertEquals(sys.stderr.getvalue(), '')
            self.patched['wakatime.offlinequeue.Queue.push'].assert_not_called()
            self.patched['wakatime.session_cache.SessionCache.get'].assert_not_called()
            self.patched['wakatime.session_cache.SessionCache.delete'].assert_not_called()
            self.patched['wakatime.session_cache.SessionCache.save'].assert_not_called()

    def test_lineno_and_cursorpos(self):
        response = Response()
        response.status_code = 0
        self.patched['wakatime.packages.requests.adapters.HTTPAdapter.send'].return_value = response

        entity = 'tests/samples/codefiles/twolinefile.txt'
        config = 'tests/samples/configs/good_config.cfg'
        now = u(int(time.time()))

        args = ['--entity', entity, '--config', config, '--time', now, '--lineno', '3', '--cursorpos', '4', '--verbose']
        retval = execute(args)

        self.assertEquals(sys.stdout.getvalue(), '')
        self.assertEquals(sys.stderr.getvalue(), '')

        self.assertEquals(retval, API_ERROR)

        self.patched['wakatime.session_cache.SessionCache.get'].assert_called_once_with()
        self.patched['wakatime.session_cache.SessionCache.delete'].assert_called_once_with()
        self.patched['wakatime.session_cache.SessionCache.save'].assert_not_called()

        heartbeat = {
            'language': 'Text only',
            'lines': 2,
            'entity': os.path.realpath(entity),
            'project': os.path.basename(os.path.abspath('.')),
            'cursorpos': '4',
            'lineno': '3',
            'branch': 'master',
            'time': float(now),
            'type': 'file',
        }
        stats = {
            u('cursorpos'): '4',
            u('dependencies'): [],
            u('language'): u('Text only'),
            u('lineno'): '3',
            u('lines'): 2,
        }

        self.patched['wakatime.offlinequeue.Queue.push'].assert_called_once_with(ANY, ANY, None)
        for key, val in self.patched['wakatime.offlinequeue.Queue.push'].call_args[0][0].items():
            self.assertEquals(heartbeat[key], val)
        self.assertEquals(stats, json.loads(self.patched['wakatime.offlinequeue.Queue.push'].call_args[0][1]))
        self.patched['wakatime.offlinequeue.Queue.pop'].assert_not_called()

    def test_non_hidden_filename(self):
        response = Response()
        response.status_code = 0
        self.patched['wakatime.packages.requests.adapters.HTTPAdapter.send'].return_value = response

        with utils.TemporaryDirectory() as tempdir:
            entity = 'tests/samples/codefiles/twolinefile.txt'
            shutil.copy(entity, os.path.join(tempdir, 'twolinefile.txt'))
            entity = os.path.realpath(os.path.join(tempdir, 'twolinefile.txt'))

            now = u(int(time.time()))
            config = 'tests/samples/configs/good_config.cfg'

            args = ['--file', entity, '--key', '123', '--config', config, '--time', now]

            retval = execute(args)
            self.assertEquals(retval, API_ERROR)
            self.assertEquals(sys.stdout.getvalue(), '')
            self.assertEquals(sys.stderr.getvalue(), '')

            self.patched['wakatime.session_cache.SessionCache.get'].assert_called_once_with()
            self.patched['wakatime.session_cache.SessionCache.delete'].assert_called_once_with()
            self.patched['wakatime.session_cache.SessionCache.save'].assert_not_called()

            heartbeat = {
                'language': 'Text only',
                'lines': 2,
                'entity': os.path.realpath(entity),
                'project': os.path.basename(os.path.abspath('.')),
                'time': float(now),
                'type': 'file',
            }
            stats = {
                u('cursorpos'): None,
                u('dependencies'): [],
                u('language'): u('Text only'),
                u('lineno'): None,
                u('lines'): 2,
            }

            self.patched['wakatime.offlinequeue.Queue.push'].assert_called_once_with(ANY, ANY, None)
            for key, val in self.patched['wakatime.offlinequeue.Queue.push'].call_args[0][0].items():
                self.assertEquals(heartbeat[key], val)
            self.assertEquals(stats, json.loads(self.patched['wakatime.offlinequeue.Queue.push'].call_args[0][1]))
            self.patched['wakatime.offlinequeue.Queue.pop'].assert_not_called()

    def test_hidden_filename(self):
        response = Response()
        response.status_code = 0
        self.patched['wakatime.packages.requests.adapters.HTTPAdapter.send'].return_value = response

        with utils.TemporaryDirectory() as tempdir:
            entity = 'tests/samples/codefiles/twolinefile.txt'
            shutil.copy(entity, os.path.join(tempdir, 'twolinefile.txt'))
            entity = os.path.realpath(os.path.join(tempdir, 'twolinefile.txt'))

            now = u(int(time.time()))
            config = 'tests/samples/configs/paranoid.cfg'

            args = ['--file', entity, '--key', '123', '--config', config, '--time', now]

            retval = execute(args)
            self.assertEquals(retval, API_ERROR)
            self.assertEquals(sys.stdout.getvalue(), '')
            self.assertEquals(sys.stderr.getvalue(), '')

            self.patched['wakatime.session_cache.SessionCache.get'].assert_called_once_with()
            self.patched['wakatime.session_cache.SessionCache.delete'].assert_called_once_with()
            self.patched['wakatime.session_cache.SessionCache.save'].assert_not_called()

            heartbeat = {
                'language': 'Text only',
                'lines': 2,
                'entity': 'HIDDEN.txt',
                'project': os.path.basename(os.path.abspath('.')),
                'time': float(now),
                'type': 'file',
            }
            stats = {
                u('cursorpos'): None,
                u('dependencies'): [],
                u('language'): u('Text only'),
                u('lineno'): None,
                u('lines'): 2,
            }

            self.patched['wakatime.offlinequeue.Queue.push'].assert_called_once_with(ANY, ANY, None)
            for key, val in self.patched['wakatime.offlinequeue.Queue.push'].call_args[0][0].items():
                self.assertEquals(heartbeat[key], val)
            self.assertEquals(stats, json.loads(self.patched['wakatime.offlinequeue.Queue.push'].call_args[0][1]))
            self.patched['wakatime.offlinequeue.Queue.pop'].assert_not_called()

    def test_invalid_timeout_passed_via_command_line(self):
        response = Response()
        response.status_code = 201
        self.patched['wakatime.packages.requests.adapters.HTTPAdapter.send'].return_value = response

        with utils.TemporaryDirectory() as tempdir:
            entity = 'tests/samples/codefiles/twolinefile.txt'
            shutil.copy(entity, os.path.join(tempdir, 'twolinefile.txt'))
            entity = os.path.realpath(os.path.join(tempdir, 'twolinefile.txt'))

            config = 'tests/samples/configs/good_config.cfg'
            args = ['--file', entity, '--key', '123', '--config', config, '--timeout', 'abc']

            with self.assertRaises(SystemExit) as e:
                execute(args)

            self.assertEquals(int(str(e.exception)), 2)
            self.assertEquals(sys.stdout.getvalue(), '')
            expected_stderr = open('tests/samples/output/main_test_timeout_passed_via_command_line').read()
            self.assertEquals(sys.stderr.getvalue(), expected_stderr)

            self.patched['wakatime.offlinequeue.Queue.push'].assert_not_called()
            self.patched['wakatime.offlinequeue.Queue.pop'].assert_not_called()
            self.patched['wakatime.session_cache.SessionCache.get'].assert_not_called()

    @log_capture()
    def test_exclude_file(self, logs):
        logging.disable(logging.NOTSET)

        response = Response()
        response.status_code = 0
        self.patched['wakatime.packages.requests.adapters.HTTPAdapter.send'].return_value = response

        with utils.TemporaryDirectory() as tempdir:
            entity = 'tests/samples/codefiles/emptyfile.txt'
            shutil.copy(entity, os.path.join(tempdir, 'emptyfile.txt'))
            entity = os.path.realpath(os.path.join(tempdir, 'emptyfile.txt'))

            config = 'tests/samples/configs/good_config.cfg'
            args = ['--file', entity, '--config', config, '--exclude', 'empty', '--verbose']
            retval = execute(args)
            self.assertEquals(retval, SUCCESS)

            self.assertEquals(sys.stdout.getvalue(), '')
            self.assertEquals(sys.stderr.getvalue(), '')

            log_output = u("\n").join([u(' ').join(x) for x in logs.actual()])
            expected = 'WakaTime DEBUG Skipping because matches exclude pattern: empty'
            self.assertEquals(log_output, expected)

            self.patched['wakatime.session_cache.SessionCache.get'].assert_not_called()
            self.patched['wakatime.session_cache.SessionCache.delete'].assert_not_called()
            self.patched['wakatime.session_cache.SessionCache.save'].assert_not_called()

            self.patched['wakatime.offlinequeue.Queue.push'].assert_not_called()
            self.patched['wakatime.offlinequeue.Queue.pop'].assert_called_once_with()

    def test_500_response(self):
        response = Response()
        response.status_code = 500
        self.patched['wakatime.packages.requests.adapters.HTTPAdapter.send'].return_value = response

        with utils.TemporaryDirectory() as tempdir:
            entity = 'tests/samples/codefiles/twolinefile.txt'
            shutil.copy(entity, os.path.join(tempdir, 'twolinefile.txt'))
            entity = os.path.realpath(os.path.join(tempdir, 'twolinefile.txt'))

            now = u(int(time.time()))

            args = ['--file', entity, '--key', '123',
                    '--config', 'tests/samples/configs/paranoid.cfg', '--time', now]

            retval = execute(args)
            self.assertEquals(retval, API_ERROR)
            self.assertEquals(sys.stdout.getvalue(), '')
            self.assertEquals(sys.stderr.getvalue(), '')

            self.patched['wakatime.session_cache.SessionCache.delete'].assert_called_once_with()
            self.patched['wakatime.session_cache.SessionCache.get'].assert_called_once_with()
            self.patched['wakatime.session_cache.SessionCache.save'].assert_not_called()

            heartbeat = {
                'language': 'Text only',
                'lines': 2,
                'entity': 'HIDDEN.txt',
                'project': os.path.basename(os.path.abspath('.')),
                'time': float(now),
                'type': 'file',
            }
            stats = {
                u('cursorpos'): None,
                u('dependencies'): [],
                u('language'): u('Text only'),
                u('lineno'): None,
                u('lines'): 2,
            }

            self.patched['wakatime.offlinequeue.Queue.push'].assert_called_once_with(ANY, ANY, None)
            for key, val in self.patched['wakatime.offlinequeue.Queue.push'].call_args[0][0].items():
                self.assertEquals(heartbeat[key], val)
            self.assertEquals(stats, json.loads(self.patched['wakatime.offlinequeue.Queue.push'].call_args[0][1]))
            self.patched['wakatime.offlinequeue.Queue.pop'].assert_not_called()

    def test_400_response(self):
        response = Response()
        response.status_code = 400
        self.patched['wakatime.packages.requests.adapters.HTTPAdapter.send'].return_value = response

        with utils.TemporaryDirectory() as tempdir:
            entity = 'tests/samples/codefiles/twolinefile.txt'
            shutil.copy(entity, os.path.join(tempdir, 'twolinefile.txt'))
            entity = os.path.realpath(os.path.join(tempdir, 'twolinefile.txt'))

            now = u(int(time.time()))

            args = ['--file', entity, '--key', '123',
                    '--config', 'tests/samples/configs/paranoid.cfg', '--time', now]

            retval = execute(args)
            self.assertEquals(retval, API_ERROR)
            self.assertEquals(sys.stdout.getvalue(), '')
            self.assertEquals(sys.stderr.getvalue(), '')

            self.patched['wakatime.session_cache.SessionCache.delete'].assert_called_once_with()
            self.patched['wakatime.session_cache.SessionCache.get'].assert_called_once_with()
            self.patched['wakatime.session_cache.SessionCache.save'].assert_not_called()

            self.patched['wakatime.offlinequeue.Queue.push'].assert_not_called()
            self.patched['wakatime.offlinequeue.Queue.pop'].assert_not_called()

    def test_401_response(self):
        response = Response()
        response.status_code = 401
        self.patched['wakatime.packages.requests.adapters.HTTPAdapter.send'].return_value = response

        with utils.TemporaryDirectory() as tempdir:
            entity = 'tests/samples/codefiles/twolinefile.txt'
            shutil.copy(entity, os.path.join(tempdir, 'twolinefile.txt'))
            entity = os.path.realpath(os.path.join(tempdir, 'twolinefile.txt'))

            now = u(int(time.time()))

            args = ['--file', entity, '--key', '123',
                    '--config', 'tests/samples/configs/paranoid.cfg', '--time', now]

            retval = execute(args)
            self.assertEquals(retval, AUTH_ERROR)
            self.assertEquals(sys.stdout.getvalue(), '')
            self.assertEquals(sys.stderr.getvalue(), '')

            self.patched['wakatime.session_cache.SessionCache.delete'].assert_called_once_with()
            self.patched['wakatime.session_cache.SessionCache.get'].assert_called_once_with()
            self.patched['wakatime.session_cache.SessionCache.save'].assert_not_called()

            heartbeat = {
                'language': 'Text only',
                'lines': 2,
                'entity': 'HIDDEN.txt',
                'project': os.path.basename(os.path.abspath('.')),
                'time': float(now),
                'type': 'file',
            }
            stats = {
                u('cursorpos'): None,
                u('dependencies'): [],
                u('language'): u('Text only'),
                u('lineno'): None,
                u('lines'): 2,
            }

            self.patched['wakatime.offlinequeue.Queue.push'].assert_called_once_with(ANY, ANY, None)
            for key, val in self.patched['wakatime.offlinequeue.Queue.push'].call_args[0][0].items():
                self.assertEquals(heartbeat[key], val)
            self.assertEquals(stats, json.loads(self.patched['wakatime.offlinequeue.Queue.push'].call_args[0][1]))
            self.patched['wakatime.offlinequeue.Queue.pop'].assert_not_called()

    @log_capture()
    def test_500_response_without_offline_logging(self, logs):
        logging.disable(logging.NOTSET)

        response = Response()
        response.status_code = 500
        response._content = 'fake content'
        if is_py3:
            response._content = 'fake content'.encode('utf8')
        self.patched['wakatime.packages.requests.adapters.HTTPAdapter.send'].return_value = response

        with utils.TemporaryDirectory() as tempdir:
            entity = 'tests/samples/codefiles/twolinefile.txt'
            shutil.copy(entity, os.path.join(tempdir, 'twolinefile.txt'))
            entity = os.path.realpath(os.path.join(tempdir, 'twolinefile.txt'))

            now = u(int(time.time()))

            args = ['--file', entity, '--key', '123', '--disableoffline',
                    '--config', 'tests/samples/configs/good_config.cfg', '--time', now]

            retval = execute(args)
            self.assertEquals(retval, API_ERROR)
            self.assertEquals(sys.stdout.getvalue(), '')
            self.assertEquals(sys.stderr.getvalue(), '')

            log_output = u("\n").join([u(' ').join(x) for x in logs.actual()])
            expected = "WakaTime ERROR {'response_code': 500, 'response_content': u'fake content'}"
            if log_output[-2] == '0':
                expected = "WakaTime ERROR {'response_content': u'fake content', 'response_code': 500}"
            if is_py3:
                expected = "WakaTime ERROR {'response_code': 500, 'response_content': 'fake content'}"
                if log_output[-2] == '0':
                    expected = "WakaTime ERROR {'response_content': 'fake content', 'response_code': 500}"
            self.assertEquals(expected, log_output)

            self.patched['wakatime.session_cache.SessionCache.delete'].assert_called_once_with()
            self.patched['wakatime.session_cache.SessionCache.get'].assert_called_once_with()
            self.patched['wakatime.session_cache.SessionCache.save'].assert_not_called()

            self.patched['wakatime.offlinequeue.Queue.push'].assert_not_called()
            self.patched['wakatime.offlinequeue.Queue.pop'].assert_not_called()

    @log_capture()
    def test_requests_exception(self, logs):
        logging.disable(logging.NOTSET)

        self.patched['wakatime.packages.requests.adapters.HTTPAdapter.send'].side_effect = RequestException('requests exception')

        with utils.TemporaryDirectory() as tempdir:
            entity = 'tests/samples/codefiles/twolinefile.txt'
            shutil.copy(entity, os.path.join(tempdir, 'twolinefile.txt'))
            entity = os.path.realpath(os.path.join(tempdir, 'twolinefile.txt'))

            now = u(int(time.time()))

            args = ['--file', entity, '--key', '123', '--verbose',
                    '--config', 'tests/samples/configs/good_config.cfg', '--time', now]

            retval = execute(args)
            self.assertEquals(retval, API_ERROR)
            self.assertEquals(sys.stdout.getvalue(), '')
            self.assertEquals(sys.stderr.getvalue(), '')

            log_output = u("\n").join([u(' ').join(x) for x in logs.actual()])
            expected = 'ImportError: No module named special'
            if is_py3:
                expected = "ImportError: No module named 'wakatime.dependencies.special'"
            self.assertIn(expected, log_output)
            expected = 'WakaTime DEBUG Sending heartbeat to api at https://api.wakatime.com/api/v1/heartbeats'
            self.assertIn(expected, log_output)
            expected = 'WakaTime DEBUG Traceback'
            self.assertIn(expected, log_output)
            expected = "RequestException': u'requests exception'"
            if is_py3:
                expected = "RequestException': 'requests exception'"
            self.assertIn(expected, log_output)

            self.patched['wakatime.session_cache.SessionCache.delete'].assert_called_once_with()
            self.patched['wakatime.session_cache.SessionCache.get'].assert_called_once_with()
            self.patched['wakatime.session_cache.SessionCache.save'].assert_not_called()

            heartbeat = {
                'language': 'Text only',
                'lines': 2,
                'entity': entity,
                'project': os.path.basename(os.path.abspath('.')),
                'time': float(now),
                'type': 'file',
            }
            stats = {
                u('cursorpos'): None,
                u('dependencies'): [],
                u('language'): u('Text only'),
                u('lineno'): None,
                u('lines'): 2,
            }

            self.patched['wakatime.offlinequeue.Queue.push'].assert_called_once_with(ANY, ANY, None)
            for key, val in self.patched['wakatime.offlinequeue.Queue.push'].call_args[0][0].items():
                self.assertEquals(heartbeat[key], val)
            self.assertEquals(stats, json.loads(self.patched['wakatime.offlinequeue.Queue.push'].call_args[0][1]))
            self.patched['wakatime.offlinequeue.Queue.pop'].assert_not_called()

    @log_capture()
    def test_requests_exception_without_offline_logging(self, logs):
        logging.disable(logging.NOTSET)

        self.patched['wakatime.packages.requests.adapters.HTTPAdapter.send'].side_effect = RequestException('requests exception')

        with utils.TemporaryDirectory() as tempdir:
            entity = 'tests/samples/codefiles/twolinefile.txt'
            shutil.copy(entity, os.path.join(tempdir, 'twolinefile.txt'))
            entity = os.path.realpath(os.path.join(tempdir, 'twolinefile.txt'))

            now = u(int(time.time()))

            args = ['--file', entity, '--key', '123', '--disableoffline',
                    '--config', 'tests/samples/configs/good_config.cfg', '--time', now]

            retval = execute(args)
            self.assertEquals(retval, API_ERROR)
            self.assertEquals(sys.stdout.getvalue(), '')
            self.assertEquals(sys.stderr.getvalue(), '')

            log_output = u("\n").join([u(' ').join(x) for x in logs.actual()])
            expected = "WakaTime ERROR {'RequestException': u'requests exception'}"
            if is_py3:
                expected = "WakaTime ERROR {'RequestException': 'requests exception'}"
            self.assertEquals(expected, log_output)

            self.patched['wakatime.session_cache.SessionCache.delete'].assert_called_once_with()
            self.patched['wakatime.session_cache.SessionCache.get'].assert_called_once_with()
            self.patched['wakatime.session_cache.SessionCache.save'].assert_not_called()

            self.patched['wakatime.offlinequeue.Queue.push'].assert_not_called()
            self.patched['wakatime.offlinequeue.Queue.pop'].assert_not_called()

    @log_capture()
    def test_missing_entity_file(self, logs):
        logging.disable(logging.NOTSET)

        response = Response()
        response.status_code = 201
        self.patched['wakatime.packages.requests.adapters.HTTPAdapter.send'].return_value = response

        entity = 'tests/samples/codefiles/missingfile.txt'

        config = 'tests/samples/configs/good_config.cfg'
        args = ['--file', entity, '--config', config, '--verbose']
        retval = execute(args)
        self.assertEquals(retval, SUCCESS)
        self.assertEquals(sys.stdout.getvalue(), '')
        self.assertEquals(sys.stderr.getvalue(), '')

        log_output = u("\n").join([u(' ').join(x) for x in logs.actual()])
        expected = 'WakaTime DEBUG File does not exist; ignoring this heartbeat.'
        self.assertEquals(log_output, expected)

        self.patched['wakatime.session_cache.SessionCache.get'].assert_not_called()
        self.patched['wakatime.session_cache.SessionCache.delete'].assert_not_called()
        self.patched['wakatime.session_cache.SessionCache.save'].assert_not_called()

        self.patched['wakatime.offlinequeue.Queue.push'].assert_not_called()
        self.patched['wakatime.offlinequeue.Queue.pop'].assert_called_once_with()

    @log_capture()
    def test_missing_entity_argument(self, logs):
        logging.disable(logging.NOTSET)

        response = Response()
        response.status_code = 201
        self.patched['wakatime.packages.requests.adapters.HTTPAdapter.send'].return_value = response

        config = 'tests/samples/configs/good_config.cfg'
        args = ['--config', config]

        with self.assertRaises(SystemExit) as e:
            execute(args)

        self.assertEquals(int(str(e.exception)), 2)
        self.assertEquals(sys.stdout.getvalue(), '')
        expected = 'error: argument --entity is required'
        self.assertIn(expected, sys.stderr.getvalue())

        log_output = u("\n").join([u(' ').join(x) for x in logs.actual()])
        expected = ''
        self.assertEquals(log_output, expected)

        self.patched['wakatime.session_cache.SessionCache.get'].assert_not_called()
        self.patched['wakatime.session_cache.SessionCache.delete'].assert_not_called()
        self.patched['wakatime.session_cache.SessionCache.save'].assert_not_called()

        self.patched['wakatime.offlinequeue.Queue.push'].assert_not_called()
        self.patched['wakatime.offlinequeue.Queue.pop'].assert_not_called()

    @log_capture()
    def test_missing_api_key(self, logs):
        logging.disable(logging.NOTSET)

        response = Response()
        response.status_code = 201
        self.patched['wakatime.packages.requests.adapters.HTTPAdapter.send'].return_value = response

        config = 'tests/samples/configs/missing_api_key.cfg'
        args = ['--config', config]

        with self.assertRaises(SystemExit) as e:
            execute(args)

        self.assertEquals(int(str(e.exception)), AUTH_ERROR)
        self.assertEquals(sys.stdout.getvalue(), '')
        expected = 'error: Missing api key'
        self.assertIn(expected, sys.stderr.getvalue())

        log_output = u("\n").join([u(' ').join(x) for x in logs.actual()])
        expected = ''
        self.assertEquals(log_output, expected)

        self.patched['wakatime.session_cache.SessionCache.get'].assert_not_called()
        self.patched['wakatime.session_cache.SessionCache.delete'].assert_not_called()
        self.patched['wakatime.session_cache.SessionCache.save'].assert_not_called()

        self.patched['wakatime.offlinequeue.Queue.push'].assert_not_called()
        self.patched['wakatime.offlinequeue.Queue.pop'].assert_not_called()

    def test_proxy_argument(self):
        response = Response()
        response.status_code = 201
        self.patched['wakatime.packages.requests.adapters.HTTPAdapter.send'].return_value = response

        with utils.TemporaryDirectory() as tempdir:
            entity = 'tests/samples/codefiles/emptyfile.txt'
            shutil.copy(entity, os.path.join(tempdir, 'emptyfile.txt'))
            entity = os.path.realpath(os.path.join(tempdir, 'emptyfile.txt'))

            config = 'tests/samples/configs/good_config.cfg'
            args = ['--file', entity, '--config', config, '--proxy', 'localhost:1234']
            retval = execute(args)
            self.assertEquals(retval, SUCCESS)
            self.assertEquals(sys.stdout.getvalue(), '')
            self.assertEquals(sys.stderr.getvalue(), '')

            self.patched['wakatime.session_cache.SessionCache.get'].assert_called_once_with()
            self.patched['wakatime.session_cache.SessionCache.delete'].assert_not_called()
            self.patched['wakatime.session_cache.SessionCache.save'].assert_called_once_with(ANY)

            self.patched['wakatime.offlinequeue.Queue.push'].assert_not_called()
            self.patched['wakatime.offlinequeue.Queue.pop'].assert_called_once_with()

            self.patched['wakatime.packages.requests.adapters.HTTPAdapter.send'].assert_called_once_with(ANY, cert=None, proxies={'https': 'localhost:1234'}, stream=False, timeout=60, verify=True)

    def test_write_argument(self):
        response = Response()
        response.status_code = 0
        self.patched['wakatime.packages.requests.adapters.HTTPAdapter.send'].return_value = response

        with utils.TemporaryDirectory() as tempdir:
            entity = 'tests/samples/codefiles/emptyfile.txt'
            shutil.copy(entity, os.path.join(tempdir, 'emptyfile.txt'))
            entity = os.path.realpath(os.path.join(tempdir, 'emptyfile.txt'))
            now = u(int(time.time()))

            args = ['--file', entity, '--key', '123', '--write', '--verbose',
                    '--config', 'tests/samples/configs/good_config.cfg', '--time', now]

            retval = execute(args)
            self.assertEquals(retval, API_ERROR)
            self.assertEquals(sys.stdout.getvalue(), '')
            self.assertEquals(sys.stderr.getvalue(), '')

            self.patched['wakatime.session_cache.SessionCache.delete'].assert_called_once_with()
            self.patched['wakatime.session_cache.SessionCache.get'].assert_called_once_with()
            self.patched['wakatime.session_cache.SessionCache.save'].assert_not_called()

            heartbeat = {
                'language': 'Text only',
                'lines': 0,
                'entity': entity,
                'project': os.path.basename(os.path.abspath('.')),
                'time': float(now),
                'type': 'file',
                'is_write': True,
            }
            stats = {
                u('cursorpos'): None,
                u('dependencies'): [],
                u('language'): u('Text only'),
                u('lineno'): None,
                u('lines'): 0,
            }

            self.patched['wakatime.offlinequeue.Queue.push'].assert_called_once_with(ANY, ANY, None)
            for key, val in self.patched['wakatime.offlinequeue.Queue.push'].call_args[0][0].items():
                self.assertEquals(heartbeat[key], val)
            self.assertEquals(stats, json.loads(self.patched['wakatime.offlinequeue.Queue.push'].call_args[0][1]))
            self.patched['wakatime.offlinequeue.Queue.pop'].assert_not_called()

    def test_entity_type_domain(self):
        response = Response()
        response.status_code = 0
        self.patched['wakatime.packages.requests.adapters.HTTPAdapter.send'].return_value = response

        entity = 'google.com'
        config = 'tests/samples/configs/good_config.cfg'
        now = u(int(time.time()))

        args = ['--entity', entity, '--entity-type', 'domain', '--config', config, '--time', now]
        retval = execute(args)

        self.assertEquals(retval, API_ERROR)
        self.assertEquals(sys.stdout.getvalue(), '')
        self.assertEquals(sys.stderr.getvalue(), '')

        self.patched['wakatime.session_cache.SessionCache.get'].assert_called_once_with()
        self.patched['wakatime.session_cache.SessionCache.delete'].assert_called_once_with()
        self.patched['wakatime.session_cache.SessionCache.save'].assert_not_called()

        heartbeat = {
            'entity': u(entity),
            'time': float(now),
            'type': 'domain',
        }
        stats = {
            u('cursorpos'): None,
            u('dependencies'): [],
            u('language'): None,
            u('lineno'): None,
            u('lines'): None,
        }

        self.patched['wakatime.offlinequeue.Queue.push'].assert_called_once_with(heartbeat, ANY, None)
        self.assertEquals(stats, json.loads(self.patched['wakatime.offlinequeue.Queue.push'].call_args[0][1]))
        self.patched['wakatime.offlinequeue.Queue.pop'].assert_not_called()

    def test_entity_type_app(self):
        response = Response()
        response.status_code = 0
        self.patched['wakatime.packages.requests.adapters.HTTPAdapter.send'].return_value = response

        entity = 'Firefox'
        config = 'tests/samples/configs/good_config.cfg'
        now = u(int(time.time()))

        args = ['--entity', entity, '--entity-type', 'app', '--config', config, '--time', now]
        retval = execute(args)

        self.assertEquals(retval, API_ERROR)
        self.assertEquals(sys.stdout.getvalue(), '')
        self.assertEquals(sys.stderr.getvalue(), '')

        self.patched['wakatime.session_cache.SessionCache.get'].assert_called_once_with()
        self.patched['wakatime.session_cache.SessionCache.delete'].assert_called_once_with()
        self.patched['wakatime.session_cache.SessionCache.save'].assert_not_called()

        heartbeat = {
            'entity': u(entity),
            'time': float(now),
            'type': 'app',
        }
        stats = {
            u('cursorpos'): None,
            u('dependencies'): [],
            u('language'): None,
            u('lineno'): None,
            u('lines'): None,
        }

        self.patched['wakatime.offlinequeue.Queue.push'].assert_called_once_with(heartbeat, ANY, None)
        self.assertEquals(stats, json.loads(self.patched['wakatime.offlinequeue.Queue.push'].call_args[0][1]))
        self.patched['wakatime.offlinequeue.Queue.pop'].assert_not_called()

    def test_nonascii_hostname(self):
        response = Response()
        response.status_code = 201
        self.patched['wakatime.packages.requests.adapters.HTTPAdapter.send'].return_value = response

        with utils.TemporaryDirectory() as tempdir:
            entity = 'tests/samples/codefiles/emptyfile.txt'
            shutil.copy(entity, os.path.join(tempdir, 'emptyfile.txt'))
            entity = os.path.realpath(os.path.join(tempdir, 'emptyfile.txt'))

            hostname = 'test汉语' if is_py3 else 'test\xe6\xb1\x89\xe8\xaf\xad'
            with utils.mock.patch('socket.gethostname') as mock_gethostname:
                mock_gethostname.return_value = hostname
                self.assertEquals(type(hostname).__name__, 'str')

                config = 'tests/samples/configs/good_config.cfg'
                args = ['--file', entity, '--config', config]
                retval = execute(args)
                self.assertEquals(retval, SUCCESS)
                self.assertEquals(sys.stdout.getvalue(), '')
                self.assertEquals(sys.stderr.getvalue(), '')

                self.patched['wakatime.session_cache.SessionCache.get'].assert_called_once_with()
                self.patched['wakatime.session_cache.SessionCache.delete'].assert_not_called()
                self.patched['wakatime.session_cache.SessionCache.save'].assert_called_once_with(ANY)

                self.patched['wakatime.offlinequeue.Queue.push'].assert_not_called()
                self.patched['wakatime.offlinequeue.Queue.pop'].assert_called_once_with()

                headers = self.patched['wakatime.packages.requests.adapters.HTTPAdapter.send'].call_args[0][0].headers
                self.assertEquals(headers.get('X-Machine-Name'), hostname.encode('utf-8') if is_py3 else hostname)

    def test_hostname_set_from_config_file(self):
        response = Response()
        response.status_code = 201
        self.patched['wakatime.packages.requests.adapters.HTTPAdapter.send'].return_value = response

        with utils.TemporaryDirectory() as tempdir:
            entity = 'tests/samples/codefiles/emptyfile.txt'
            shutil.copy(entity, os.path.join(tempdir, 'emptyfile.txt'))
            entity = os.path.realpath(os.path.join(tempdir, 'emptyfile.txt'))

            hostname = 'fromcfgfile'
            config = 'tests/samples/configs/has_everything.cfg'
            args = ['--file', entity, '--config', config, '--timeout', '15']
            retval = execute(args)
            self.assertEquals(retval, SUCCESS)

            self.patched['wakatime.session_cache.SessionCache.get'].assert_called_once_with()
            self.patched['wakatime.session_cache.SessionCache.delete'].assert_not_called()
            self.patched['wakatime.session_cache.SessionCache.save'].assert_called_once_with(ANY)

            self.patched['wakatime.offlinequeue.Queue.push'].assert_not_called()
            self.patched['wakatime.offlinequeue.Queue.pop'].assert_called_once_with()

            headers = self.patched['wakatime.packages.requests.adapters.HTTPAdapter.send'].call_args[0][0].headers
            self.assertEquals(headers.get('X-Machine-Name'), hostname.encode('utf-8') if is_py3 else hostname)

    def test_nonascii_timezone(self):
        response = Response()
        response.status_code = 201
        self.patched['wakatime.packages.requests.adapters.HTTPAdapter.send'].return_value = response

        with utils.TemporaryDirectory() as tempdir:
            entity = 'tests/samples/codefiles/emptyfile.txt'
            shutil.copy(entity, os.path.join(tempdir, 'emptyfile.txt'))
            entity = os.path.realpath(os.path.join(tempdir, 'emptyfile.txt'))

            class TZ(object):
                @property
                def zone(self):
                    return 'tz汉语' if is_py3 else 'tz\xe6\xb1\x89\xe8\xaf\xad'
            timezone = TZ()

            with utils.mock.patch('wakatime.packages.tzlocal.get_localzone') as mock_getlocalzone:
                mock_getlocalzone.return_value = timezone

                config = 'tests/samples/configs/has_everything.cfg'
                args = ['--file', entity, '--config', config, '--timeout', '15']
                retval = execute(args)
                self.assertEquals(retval, SUCCESS)

                self.patched['wakatime.session_cache.SessionCache.get'].assert_called_once_with()
                self.patched['wakatime.session_cache.SessionCache.delete'].assert_not_called()
                self.patched['wakatime.session_cache.SessionCache.save'].assert_called_once_with(ANY)

                self.patched['wakatime.offlinequeue.Queue.push'].assert_not_called()
                self.patched['wakatime.offlinequeue.Queue.pop'].assert_called_once_with()

                headers = self.patched['wakatime.packages.requests.adapters.HTTPAdapter.send'].call_args[0][0].headers
                self.assertEquals(headers.get('TimeZone'), u(timezone.zone).encode('utf-8') if is_py3 else timezone.zone)

    def test_timezone_with_invalid_encoding(self):
        response = Response()
        response.status_code = 201
        self.patched['wakatime.packages.requests.adapters.HTTPAdapter.send'].return_value = response

        with utils.TemporaryDirectory() as tempdir:
            entity = 'tests/samples/codefiles/emptyfile.txt'
            shutil.copy(entity, os.path.join(tempdir, 'emptyfile.txt'))
            entity = os.path.realpath(os.path.join(tempdir, 'emptyfile.txt'))

            class TZ(object):
                @property
                def zone(self):
                    return bytes('\xab', 'utf-16') if is_py3 else '\xab'
            timezone = TZ()

            with self.assertRaises(UnicodeDecodeError):
                timezone.zone.decode('utf8')

            with utils.mock.patch('wakatime.packages.tzlocal.get_localzone') as mock_getlocalzone:
                mock_getlocalzone.return_value = timezone

                config = 'tests/samples/configs/has_everything.cfg'
                args = ['--file', entity, '--config', config, '--timeout', '15']
                retval = execute(args)
                self.assertEquals(retval, SUCCESS)

                self.patched['wakatime.session_cache.SessionCache.get'].assert_called_once_with()
                self.patched['wakatime.session_cache.SessionCache.delete'].assert_not_called()
                self.patched['wakatime.session_cache.SessionCache.save'].assert_called_once_with(ANY)

                self.patched['wakatime.offlinequeue.Queue.push'].assert_not_called()
                self.patched['wakatime.offlinequeue.Queue.pop'].assert_called_once_with()

    def test_tzlocal_exception(self):
        response = Response()
        response.status_code = 201
        self.patched['wakatime.packages.requests.adapters.HTTPAdapter.send'].return_value = response

        with utils.TemporaryDirectory() as tempdir:
            entity = 'tests/samples/codefiles/emptyfile.txt'
            shutil.copy(entity, os.path.join(tempdir, 'emptyfile.txt'))
            entity = os.path.realpath(os.path.join(tempdir, 'emptyfile.txt'))

            with utils.mock.patch('wakatime.packages.tzlocal.get_localzone') as mock_getlocalzone:
                mock_getlocalzone.side_effect = Exception('tzlocal exception')

                config = 'tests/samples/configs/has_everything.cfg'
                args = ['--file', entity, '--config', config, '--timeout', '15']
                retval = execute(args)
                self.assertEquals(retval, SUCCESS)

                self.patched['wakatime.session_cache.SessionCache.get'].assert_called_once_with()
                self.patched['wakatime.session_cache.SessionCache.delete'].assert_not_called()
                self.patched['wakatime.session_cache.SessionCache.save'].assert_called_once_with(ANY)

                self.patched['wakatime.offlinequeue.Queue.push'].assert_not_called()
                self.patched['wakatime.offlinequeue.Queue.pop'].assert_called_once_with()

                headers = self.patched['wakatime.packages.requests.adapters.HTTPAdapter.send'].call_args[0][0].headers
                self.assertEquals(headers.get('TimeZone'), None)

    def test_timezone_header(self):
        response = Response()
        response.status_code = 201
        self.patched['wakatime.packages.requests.adapters.HTTPAdapter.send'].return_value = response

        with utils.TemporaryDirectory() as tempdir:
            entity = 'tests/samples/codefiles/emptyfile.txt'
            shutil.copy(entity, os.path.join(tempdir, 'emptyfile.txt'))
            entity = os.path.realpath(os.path.join(tempdir, 'emptyfile.txt'))

            config = 'tests/samples/configs/good_config.cfg'
            args = ['--file', entity, '--config', config]
            retval = execute(args)
            self.assertEquals(retval, SUCCESS)
            self.assertEquals(sys.stdout.getvalue(), '')
            self.assertEquals(sys.stderr.getvalue(), '')

            self.patched['wakatime.session_cache.SessionCache.get'].assert_called_once_with()
            self.patched['wakatime.session_cache.SessionCache.delete'].assert_not_called()
            self.patched['wakatime.session_cache.SessionCache.save'].assert_called_once_with(ANY)

            self.patched['wakatime.offlinequeue.Queue.push'].assert_not_called()
            self.patched['wakatime.offlinequeue.Queue.pop'].assert_called_once_with()

            timezone = tzlocal.get_localzone()
            headers = self.patched['wakatime.packages.requests.adapters.HTTPAdapter.send'].call_args[0][0].headers
            self.assertEquals(headers.get('TimeZone'), u(timezone.zone).encode('utf-8') if is_py3 else timezone.zone)

    def test_extra_heartbeats_argument(self):
        response = Response()
        response.status_code = 201
        self.patched['wakatime.packages.requests.adapters.HTTPAdapter.send'].return_value = response

        with utils.TemporaryDirectory() as tempdir:
            entity = 'tests/samples/codefiles/twolinefile.txt'
            shutil.copy(entity, os.path.join(tempdir, 'twolinefile.txt'))
            entity = os.path.realpath(os.path.join(tempdir, 'twolinefile.txt'))

            project1 = os.path.basename(os.path.abspath('.'))
            project2 = 'xyz'
            entity1 = os.path.abspath('tests/samples/codefiles/emptyfile.txt')
            entity2 = os.path.abspath('tests/samples/codefiles/twolinefile.txt')
            config = 'tests/samples/configs/good_config.cfg'
            args = ['--file', entity1, '--config', config, '--extra-heartbeats']

            with utils.mock.patch('wakatime.main.sys.stdin') as mock_stdin:
                now = int(time.time())
                heartbeats = json.dumps([{
                    'timestamp': now,
                    'entity': entity2,
                    'entity_type': 'file',
                    'project': project2,
                    'is_write': True,
                }])
                mock_stdin.readline.return_value = heartbeats

                retval = execute(args)

                self.assertEquals(retval, SUCCESS)
                self.assertEquals(sys.stdout.getvalue(), '')
                self.assertEquals(sys.stderr.getvalue(), '')

                self.patched['wakatime.session_cache.SessionCache.get'].assert_has_calls([call(), call()])
                self.patched['wakatime.session_cache.SessionCache.delete'].assert_not_called()
                self.patched['wakatime.session_cache.SessionCache.save'].assert_has_calls([call(ANY), call(ANY)])

                self.patched['wakatime.offlinequeue.Queue.push'].assert_not_called()
                self.patched['wakatime.offlinequeue.Queue.pop'].assert_called_once_with()

                calls = self.patched['wakatime.packages.requests.adapters.HTTPAdapter.send'].call_args_list

                body = calls[0][0][0].body
                data = json.loads(body)
                self.assertEquals(data.get('entity'), entity1)
                self.assertEquals(data.get('project'), project1)

                body = calls[1][0][0].body
                data = json.loads(body)
                self.assertEquals(data.get('entity'), entity2)
                self.assertEquals(data.get('project'), project2)

    @log_capture()
    def test_extra_heartbeats_with_malformed_json(self, logs):
        logging.disable(logging.NOTSET)

        response = Response()
        response.status_code = 201
        self.patched['wakatime.packages.requests.adapters.HTTPAdapter.send'].return_value = response

        with utils.TemporaryDirectory() as tempdir:
            entity = 'tests/samples/codefiles/twolinefile.txt'
            shutil.copy(entity, os.path.join(tempdir, 'twolinefile.txt'))
            entity = os.path.realpath(os.path.join(tempdir, 'twolinefile.txt'))

            entity = os.path.abspath('tests/samples/codefiles/emptyfile.txt')
            config = 'tests/samples/configs/good_config.cfg'
            args = ['--file', entity, '--config', config, '--extra-heartbeats']

            with utils.mock.patch('wakatime.main.sys.stdin') as mock_stdin:
                heartbeats = '[{foobar}]'
                mock_stdin.readline.return_value = heartbeats

                retval = execute(args)

                self.assertEquals(retval, MALFORMED_HEARTBEAT_ERROR)
                self.assertEquals(sys.stdout.getvalue(), '')
                self.assertEquals(sys.stderr.getvalue(), '')

                log_output = u("\n").join([u(' ').join(x) for x in logs.actual()])
                self.assertEquals(log_output, '')

                self.patched['wakatime.session_cache.SessionCache.get'].assert_called_once_with()
                self.patched['wakatime.session_cache.SessionCache.delete'].assert_not_called()
                self.patched['wakatime.session_cache.SessionCache.save'].assert_called_once_with(ANY)

                self.patched['wakatime.offlinequeue.Queue.push'].assert_not_called()
                self.patched['wakatime.offlinequeue.Queue.pop'].assert_not_called()

    @log_capture()
    def test_nonascii_filename(self, logs):
        logging.disable(logging.NOTSET)

        response = Response()
        response.status_code = 0
        self.patched['wakatime.packages.requests.adapters.HTTPAdapter.send'].return_value = response

        with utils.TemporaryDirectory() as tempdir:
            filename = os.listdir('tests/samples/codefiles/unicode')[0]
            entity = os.path.join('tests/samples/codefiles/unicode', filename)
            shutil.copy(entity, os.path.join(tempdir, filename))
            entity = os.path.realpath(os.path.join(tempdir, filename))

            now = u(int(time.time()))
            config = 'tests/samples/configs/good_config.cfg'

            args = ['--file', entity, '--key', '123', '--config', config, '--time', now]

            retval = execute(args)
            self.assertEquals(retval, API_ERROR)
            self.assertEquals(sys.stdout.getvalue(), '')
            self.assertEquals(sys.stderr.getvalue(), '')

            output = [u(' ').join(x) for x in logs.actual()]
            self.assertEquals(len(output), 0)

            self.patched['wakatime.session_cache.SessionCache.get'].assert_called_once_with()
            self.patched['wakatime.session_cache.SessionCache.delete'].assert_called_once_with()
            self.patched['wakatime.session_cache.SessionCache.save'].assert_not_called()

            heartbeat = {
                'language': 'Text only',
                'lines': 0,
                'entity': os.path.realpath(entity),
                'project': os.path.basename(os.path.abspath('.')),
                'time': float(now),
                'type': 'file',
            }
            stats = {
                u('cursorpos'): None,
                u('dependencies'): [],
                u('language'): u('Text only'),
                u('lineno'): None,
                u('lines'): 0,
            }

            self.patched['wakatime.offlinequeue.Queue.push'].assert_called_once_with(ANY, ANY, None)
            for key, val in self.patched['wakatime.offlinequeue.Queue.push'].call_args[0][0].items():
                self.assertEquals(heartbeat[key], val)
            self.assertEquals(stats, json.loads(self.patched['wakatime.offlinequeue.Queue.push'].call_args[0][1]))
            self.patched['wakatime.offlinequeue.Queue.pop'].assert_not_called()

    @log_capture()
    def test_unhandled_exception(self, logs):
        logging.disable(logging.NOTSET)

        with utils.mock.patch('wakatime.main.process_heartbeat') as mock_process_heartbeat:
            ex_msg = 'testing unhandled exception'
            mock_process_heartbeat.side_effect = RuntimeError(ex_msg)

            entity = 'tests/samples/codefiles/twolinefile.txt'
            config = 'tests/samples/configs/good_config.cfg'
            args = ['--entity', entity, '--key', '123', '--config', config]

            execute(args)

            self.assertIn(ex_msg, sys.stdout.getvalue())
            self.assertEquals(sys.stderr.getvalue(), '')

            log_output = u("\n").join([u(' ').join(x) for x in logs.actual()])
            self.assertIn(ex_msg, log_output)

            self.patched['wakatime.offlinequeue.Queue.push'].assert_not_called()
            self.patched['wakatime.offlinequeue.Queue.pop'].assert_not_called()
            self.patched['wakatime.session_cache.SessionCache.get'].assert_not_called()
