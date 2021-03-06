from __future__ import unicode_literals

import datetime
from decimal import Decimal

from django.db.models.fields.files import FieldFile
from django.test import TestCase, RequestFactory
from mock import patch, MagicMock
from psutil import Process

from audit_tools.audit import utils
from audit_tools.audit.utils import filter_request_meta, i18n_url


class DynamicImportTestCase(TestCase):
    def setUp(self):
        pass

    def test_import_incorrect_str(self):
        callable_str = 'audit_tools#audit#utils#dynamic_import'
        self.assertRaises(ValueError, utils.dynamic_import, callable_str)

    def test_import_module_not_exists(self):
        callable_str = 'audit_tools.audit.foo.bar'
        self.assertRaises(ImportError, utils.dynamic_import, callable_str)

    def test_import_ok(self):
        callable_str = 'audit_tools.audit.utils.dynamic_import'
        function = utils.dynamic_import(callable_str)
        self.assertEqual(function, utils.dynamic_import)

    def tearDown(self):
        pass


class RequestUtilsTestCase(TestCase):
    def setUp(self):
        pass

    @patch('audit_tools.audit.utils.os')
    def test_filter_request_meta(self, os=None):
        os.environ.keys.return_value = {
            'test': 1,
            'test2': 2
        }

        initial_dict = {
            'test': 1,
            'test2': 2,
            'test3': 3
        }
        filtered_dict = utils.filter_request_meta(initial_dict)

        self.assertDictEqual(filtered_dict, {'test3': 3})

    def test_parse_request_meta(self):
        request_factory = RequestFactory()
        request = request_factory.get('/test', data={'foo': 'bar'})

        metadata = utils.parse_request_meta(str(request.META))

        self.assertEqual(len(metadata), len(request.META))

    def test_request_to_dict(self):
        request_factory = RequestFactory()
        request = request_factory.get('/test', data={'foo': 'bar'})

        request_dict = utils.request_to_dict(request)

        self.assertEqual(request_dict['path'], '/test')
        self.assertEqual(len(request_dict['GET']), len(request.GET))
        self.assertEqual(len(request_dict['POST']), len(request.POST))
        self.assertEqual(len(request_dict['COOKIES']), len(request.COOKIES))
        self.assertEqual(len(request_dict['METADATA']), len(request.META))
        self.assertIsNone(request_dict['RAW_METADATA'])

    def test_request_to_dict_fail(self):
        effects = ('get', 'post', 'cookies', ValueError)
        with patch('audit_tools.audit.utils.fix_dict', side_effect=effects):
            request_factory = RequestFactory()
            request = request_factory.get('/test', data={'foo': 'bar'})

            request_dict = utils.request_to_dict(request)

            self.assertEqual(request_dict['path'], '/test')
            self.assertEqual(request_dict['GET'], 'get')
            self.assertEqual(request_dict['POST'], 'post')
            self.assertEqual(request_dict['COOKIES'], 'cookies')
            self.assertIsNone(request_dict['METADATA'])
            self.assertEqual(len(request_dict['RAW_METADATA']), len(str(filter_request_meta(request.META))))

    def tearDown(self):
        pass


class UtilsTestCase(TestCase):
    def setUp(self):
        pass

    def test_fix_dict(self):
        initial_dict = {
            'foo.bar': 'foo',
            'bar$foo': 'bar'
        }

        fixed_dict = utils.fix_dict(initial_dict)
        self.assertDictEqual(fixed_dict, {'foo_bar': 'foo', 'bar_foo': 'bar'})

    @patch('audit_tools.audit.utils.dynamic_import', return_value=True)
    @patch('audit_tools.audit.utils.settings')
    def test_import_providers(self, settings, dynamic_import):
        settings.CUSTOM_PROVIDER = {'foo': 'foo.bar'}
        expected_result = {'foo': True}

        providers = utils.import_providers()

        self.assertDictEqual(expected_result, providers)

    @patch('audit_tools.audit.utils.model_to_dict')
    def test_serialize_model_instance(self, model_to_dict):
        model_to_dict.return_value = {
            'date': datetime.date(2014, 12, 31),
            'time': datetime.time(0, 0, 0),
            'decimal': Decimal(1.0),
            'str': b'str',
            'unicode': 'unicode',
            'file': FieldFile(instance=None, field=MagicMock(), name='foo')
        }

        expected_result = {
            'date': datetime.datetime(2014, 12, 31),
            'time': datetime.datetime(1, 1, 1, 0, 0, 0),
            'decimal': 1.0,
            'str': 'str',
            'unicode': 'unicode',
            'file': 'foo'
        }

        serialized_instance = utils.serialize_model_instance(None)

        self.assertDictEqual(expected_result, serialized_instance)

    @patch('audit_tools.audit.utils.sys')
    @patch.object(Process, 'username', return_value='Username')
    @patch.object(Process, 'pid', 1)
    @patch('audit_tools.audit.utils.socket')
    @patch('audit_tools.audit.utils.get_process_interlink_id', return_value='Interlink ID')
    def test_extract_process_data(self, interlink, socket, process, sys):
        socket.gethostname.return_value = 'Machine'
        sys.argv = ['foo', 'b', 'a', 'r']

        process_data = utils.extract_process_data()

        self.assertEqual(process_data['interlink_id'], 'Interlink ID')
        self.assertEqual(process_data['user'], 'Username')
        self.assertEqual(process_data['pid'], 1)
        self.assertEqual(process_data['machine'], 'Machine')
        self.assertEqual(process_data['name'], 'foo')
        self.assertEqual(process_data['args'], 'b a r')
        self.assertIn('creation_time', process_data)

    @patch('audit_tools.audit.utils.sys')
    @patch.object(Process, 'username', return_value='Username')
    @patch.object(Process, 'pid', 1)
    @patch('audit_tools.audit.utils.socket')
    @patch('audit_tools.audit.utils.get_process_interlink_id', return_value='Interlink ID')
    def test_extract_process_data_managepy(self, interlink, socket, process, sys):
        socket.gethostname.return_value = 'Machine'
        sys.argv = ['manage.py', 'foo', 'b', 'a', 'r']

        process_data = utils.extract_process_data()

        self.assertEqual(process_data['interlink_id'], 'Interlink ID')
        self.assertEqual(process_data['user'], 'Username')
        self.assertEqual(process_data['pid'], 1)
        self.assertEqual(process_data['machine'], 'Machine')
        self.assertEqual(process_data['name'], 'foo')
        self.assertEqual(process_data['args'], 'b a r')
        self.assertIn('creation_time', process_data)

    @patch('audit_tools.audit.utils.settings')
    def test_i18n_url(self, settings):
        settings.TRANSLATE_URLS = True
        url = 'foo'

        res = i18n_url(url)

        self.assertFalse(isinstance(res, str))

    @patch('audit_tools.audit.utils.settings')
    def test_i18n_url_deactivated(self, settings):
        settings.TRANSLATE_URLS = False
        url = 'foo'

        res = i18n_url(url)

        self.assertEqual(url, res)

    def tearDown(self):
        pass
