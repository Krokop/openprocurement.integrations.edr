# -*- coding: utf-8 -*-
import webtest
import os

from openprocurement.integrations.edr.tests.base import BaseWebTest
from openprocurement.integrations.edr.tests._server import setup_routing, response_code, response_passport, check_headers, \
    payment_required, forbidden, not_acceptable, too_many_requests, two_error_messages, bad_gateway, server_error


class TestVerify(BaseWebTest):
    """ Test verify view """

    def test_edrpou(self):
        """ Get info by custom edrpou """
        setup_routing(self.edr_api_app, func=response_code)
        response = self.app.get('/verify/14360570')
        self.assertEqual(response.status, '200 OK')
        self.assertEqual(response.content_type, 'application/json')
        self.assertEqual(
            response.json['data'],
            {
                u'code': u'14360570',
                u'name': u"АКЦІОНЕРНЕ ТОВАРИСТВО КОМЕРЦІЙНИЙ БАНК \"ПРИВАТБАНК\"",
                u'url': u'https://zqedr-api.nais.gov.ua/1.0/subjects/2842335',
                u'state': 1,
                u'state_text': u'https://zqedr-api.nais.gov.ua/1.0/subjects/2842335',
                u'id': 2842335
            })

    def test_passport(self):
        """ Get info by passport number """
        setup_routing(self.edr_api_app, func=response_passport)
        response = self.app.get('/verify/СН012345')
        self.assertEqual(response.status, '200 OK')
        self.assertEqual(response.content_type, 'application/json')
        self.assertEqual(
            response.json['data'],
            {
                u'code': u'СН012345',
                u'name': u'СН012345',
                u'url': u'https://zqedr-api.nais.gov.ua/1.0/subjects/2842336',
                u'state': 1,
                u'state_text': u'https://zqedr-api.nais.gov.ua/1.0/subjects/2842336',
                u'id': 2842336
            })

    def test_new_passport(self):
        """ Get info by new passport number with 13-digits"""
        setup_routing(self.edr_api_app, func=response_passport)
        response = self.app.get('/verify/123456789')
        self.assertEqual(response.status, '200 OK')
        self.assertEqual(response.content_type, 'application/json')
        self.assertEqual(
            response.json['data'],
            {
                u'code': u'123456789',
                u'name': u'123456789',
                u'url': u'https://zqedr-api.nais.gov.ua/1.0/subjects/2842336',
                u'state': 1,
                u'state_text': u'https://zqedr-api.nais.gov.ua/1.0/subjects/2842336',
                u'id': 2842336
            })

    def test_ipn(self):
        """ Get info by IPN (physical entity-entrepreneur)"""
        setup_routing(self.edr_api_app, func=response_code)
        response = self.app.get('/verify/1234567891')
        self.assertEqual(response.status, '200 OK')
        self.assertEqual(response.content_type, 'application/json')
        self.assertEqual(response.json['data'],
            {
                u'code': u'1234567891',
                u'name': u"АКЦІОНЕРНЕ ТОВАРИСТВО КОМЕРЦІЙНИЙ БАНК \"ПРИВАТБАНК\"",
                u'url': u'https://zqedr-api.nais.gov.ua/1.0/subjects/2842335',
                u'state': 1,
                u'state_text': u'https://zqedr-api.nais.gov.ua/1.0/subjects/2842335',
                u'id': 2842335
            })

    def test_invalid_passport(self):
        """Check invalid passport number АБВ"""
        setup_routing(self.edr_api_app, func=response_passport)
        response = self.app.get('/verify/АБВ', status=403)
        self.assertEqual(response.status, '403 Forbidden')
        self.assertEqual(response.content_type, 'application/json')
        self.assertEqual(response.json['errors'][0]['description'],  [u'`passport` parameter has wrong value.'])

    def test_invalid_code(self):
        """Check invalid EDRPOU(IPN) number 123"""
        setup_routing(self.edr_api_app, func=response_code)
        response = self.app.get('/verify/123', status=403)
        self.assertEqual(response.content_type, 'application/json')
        self.assertEqual(response.status, '403 Forbidden')
        self.assertEqual(response.json['errors'][0]['description'], [u'EDRPOU not found'])

    def test_unauthorized(self):
        """Send request without token using tests_copy.ini conf file"""
        setup_routing(self.edr_api_app, func=check_headers)
        self.app_copy = webtest.TestApp("config:test_conf/tests_copy.ini", relative_to=os.path.dirname(__file__))
        self.app_copy.authorization = ('Basic', ('token', ''))
        response = self.app_copy.get('/api/2.3/verify/123', status=403)
        self.assertEqual(response.content_type, 'application/json')
        self.assertEqual(response.status, '403 Forbidden')
        self.assertEqual(response.json['errors'][0]['description'], [u'Authentication credentials were not provided.'])

    def test_payment_required(self):
        """Check 402 status EDR response"""
        setup_routing(self.edr_api_app, func=payment_required)
        response = self.app.get('/verify/14360570', status=403)
        self.assertEqual(response.content_type, 'application/json')
        self.assertEqual(response.status, '403 Forbidden')
        self.assertEqual(response.json['errors'][0]['description'], [u'Paiment required.'])

    def test_forbidden(self):
        """Check 403 status EDR response"""
        setup_routing(self.edr_api_app, func=forbidden)
        response = self.app.get('/verify/14360570', status=403)
        self.assertEqual(response.content_type, 'application/json')
        self.assertEqual(response.status, '403 Forbidden')
        self.assertEqual(response.json['errors'][0]['description'],
                         [u'Your account is not permitted to access this resource.'])

    def test_invalid_token(self):
        """Send request with invalid token 123 using new tests_copy_2.ini conf file"""
        setup_routing(self.edr_api_app, func=check_headers)
        self.app_copy = webtest.TestApp("config:test_conf/tests_copy_2.ini", relative_to=os.path.dirname(__file__))
        self.app_copy.authorization = ('Basic', ('token', ''))
        response = self.app_copy.get('/api/2.3/verify/123', status=403)
        self.assertEqual(response.content_type, 'application/json')
        self.assertEqual(response.status, '403 Forbidden')
        self.assertEqual(response.json['errors'][0]['description'], [u'Invalid or expired token.'])

    def test_not_acceptable(self):
        """Check 406 status EDR response"""
        setup_routing(self.edr_api_app, func=not_acceptable)
        response = self.app.get('/verify/123', status=403)
        self.assertEqual(response.content_type, 'application/json')
        self.assertEqual(response.status, '403 Forbidden')
        self.assertEqual(response.json['errors'][0]['description'], [u'Message.'])

    def test_too_many_requests(self):
        """Check 429 status EDR response(too many requests)"""
        setup_routing(self.edr_api_app, func=too_many_requests)
        response = self.app.get('/verify/123', status=403)
        self.assertEqual(response.content_type, 'application/json')
        self.assertEqual(response.status, '403 Forbidden')
        self.assertEqual(response.json['errors'][0]['description'], [u'Retry request after 26 seconds.'])

    def test_server_error(self):
        """Check 500 status EDR response"""
        setup_routing(self.edr_api_app, func=server_error)
        response = self.app.get('/verify/123', status=403)
        self.assertEqual(response.content_type, 'application/json')
        self.assertEqual(response.status, '403 Forbidden')
        self.assertEqual(response.json['errors'][0]['description'], [u'Internal error.'])

    def test_bad_gateway(self):
        """Check 502 status EDR response"""
        setup_routing(self.edr_api_app, func=bad_gateway)
        response = self.app.get('/verify/123', status=403)
        self.assertEqual(response.content_type, 'application/json')
        self.assertEqual(response.status, '403 Forbidden')
        self.assertEqual(response.json['errors'][0]['description'], [u'Service is disabled or upgrade.'])

    def test_two_error_messages(self):
        """Check when EDR passes two errors in response"""
        setup_routing(self.edr_api_app, func=two_error_messages)
        response = self.app.get('/verify/123', status=403)
        self.assertEqual(response.content_type, 'application/json')
        self.assertEqual(response.status, '403 Forbidden')
        self.assertEqual(response.json['errors'][0]['description'], [u'Message1.', u'Message2.'])

    def test_long_edrpou(self):
        setup_routing(self.edr_api_app, func=response_passport)
        response = self.app.get('/verify/12345678912', status=403)
        self.assertEqual(response.status, '403 Forbidden')
        self.assertEqual(response.content_type, 'application/json')
        self.assertEqual(response.json['errors'][0]['description'], [u'`passport` parameter has wrong value.'])