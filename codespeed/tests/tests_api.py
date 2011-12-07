# -*- coding: utf-8 -*-

"""
Tests related to RESTful API
"""

from datetime import datetime
import copy, json
import logging
import unittest

from django import test
from django.db.utils import IntegrityError
from django.test.client import Client
from django.http import HttpRequest
from django.core.urlresolvers import reverse
from django.conf import settings
from django.contrib.auth.models import User
from tastypie.exceptions import ImmediateHttpResponse
from tastypie.models import ApiKey, create_api_key
from tastypie.http import HttpUnauthorized
from tastypie.authentication import Authentication, ApiKeyAuthentication
from codespeed.models import (Project, Benchmark, Revision, Branch,
                              Executable, Environment, Result, Report)
from codespeed.api import ResultBundle

from codespeed import settings as default_settings


class FixtureTestCase(test.TestCase):
    fixtures = ["gettimeline_unittest.json"]

    def setUp(self):
        self.api_user = User.objects.create_user(
            username='apiuser', email='api@foo.bar', password='password')
        self.api_user.save()


class EnvironmentTest(FixtureTestCase):
    """Test Environment() API
    """

    def setUp(self):
        self.env1_data = dict(
            name="env1",
            cpu="cpu1",
            memory="48kB",
            os="ZX Spectrum OS",
            kernel="2.6.32"
        )
        self.env1 = Environment(**self.env1_data)
        self.env1.save()
        self.env2_data = dict(
            name="env2",
            cpu="z80",
            memory="64kB",
            os="ZX Spectrum OS",
            kernel="2.6.32"
        )
        self.client = Client()
        super(EnvironmentTest, self).setUp()

    def test_get_environment(self):
        """Should get an existing environment"""
        response = self.client.get('/api/v1/environment/1/')
        self.assertEquals(response.status_code, 200)
        self.assertEqual(json.loads(response.content)['name'], "Dual Core")

    def test_get_environment_all_fields(self):
        """Should get all fields for an environment"""
        response = self.client.get('/api/v1/environment/%s/' % (self.env1.id,))
        self.assertEquals(response.status_code, 200)
        for k in self.env1_data.keys():
            self.assertEqual(
                json.loads(response.content)[k], getattr(self.env1, k))

    def test_post(self):
        """Should save a new environment"""
        response = self.client.post('/api/v1/environment/',
                                    data=json.dumps(self.env2_data),
                                    content_type='application/json')
        self.assertEquals(response.status_code, 201)
        response = self.client.get('/api/v1/environment/3/')
        for k, v in self.env2_data.items():
            self.assertEqual(
                json.loads(response.content)[k], v)

    def test_put(self):
        """Should modify an existing environment"""
        modified_data = copy.deepcopy(self.env2_data)
        modified_data['name'] = "env2.2"
        modified_data['memory'] = "128kB"
        response = self.client.put('/api/v1/environment/3/',
                                    data=json.dumps(modified_data),
                                    content_type='application/json')
        self.assertEquals(response.status_code, 201)
        response = self.client.get('/api/v1/environment/3/')
        for k, v in modified_data.items():
            self.assertEqual(
                json.loads(response.content)[k], v)

    def test_delete(self):
        """Should delete an environment"""
        response = self.client.get('/api/v1/environment/{0}/'.format(self.env1.id))
        self.assertEquals(response.status_code, 200)
        response = self.client.delete('/api/v1/environment/{0}/'.format(self.env1.id),
                                    content_type='application/json')
        self.assertEquals(response.status_code, 204)

        response = self.client.get('/api/v1/environment/{0}/'.format(self.env1.id))
        self.assertEquals(response.status_code, 410)


class ProjectTest(FixtureTestCase):
    """Test Environment() API
    """

    def setUp(self):
        self.project_data = dict(
            name="PyPy",
            repo_type="M",
            repo_path="ssh://hg@bitbucket.org/pypy/pypy",
            repo_user="fridolin",
            repo_pass="secret",
        )
        self.project_data2 = dict(
            name="project alpha",
            repo_type="M",
            repo_path="ssh://hg@bitbucket.org/pypy/pypy",
            repo_user="alpha",
            repo_pass="beta",
            )
        self.project = Project(**self.project_data)
        self.project.save()
        self.client = Client()
        super(ProjectTest, self).setUp()

    def test_get_project(self):
        """Should get an existing project"""
        response = self.client.get('/api/v1/project/{0}/'.format(self.project.id,))
        self.assertEquals(response.status_code, 200)
        self.assertEqual(json.loads(response.content)['name'], "{0}".format(self.project_data['name']))

    def test_get_project_all_fields(self):
        """Should get all fields for an environment"""
        response = self.client.get('/api/v1/project/%s/' % (self.project.id,))
        self.assertEquals(response.status_code, 200)
        for k in self.project_data.keys():
            self.assertEqual(
                json.loads(response.content)[k], getattr(self.project, k))

    def test_post(self):
        """Should save a new project"""
        response = self.client.post('/api/v1/project/',
                                    data=json.dumps(self.project_data2),
                                    content_type='application/json')
        self.assertEquals(response.status_code, 201)
        response = self.client.get('/api/v1/project/{0}/'.format(self.project.id))
        for k, v in self.project_data.items():
            self.assertEqual(
                json.loads(response.content)[k], v)

    def test_delete(self):
        """Should delete an project"""
        response = self.client.delete('/api/v1/project/{0}/'.format(self.project.id,),
                                    content_type='application/json')
        self.assertEquals(response.status_code, 204)

        response = self.client.get('/api/v1/project/{0}/'.format(self.project.id,))
        self.assertEquals(response.status_code, 410)


class UserTest(FixtureTestCase):
    """Test api user related stuff
    """

    def test_has_apikey(self):
        self.assertTrue(hasattr(self.api_user, 'api_key'))


class ApiKeyAuthenticationTestCase(FixtureTestCase):

    def setUp(self):
        super(ApiKeyAuthenticationTestCase, self).setUp()
        ApiKey.objects.all().delete()
        self.auth = ApiKeyAuthentication()
        self.request = HttpRequest()

        # Simulate sending the signal.
        user = User.objects.get(username='apiuser')
        create_api_key(User, instance=user, created=True)

    def test_is_not_authenticated(self):
        """Should return HttpUnauthorized when incorrect credentials are given"""
        # No username/api_key details
        self.assertEqual(isinstance(
            self.auth.is_authenticated(self.request), HttpUnauthorized), True)

        # Wrong username details.
        self.request.GET['username'] = 'foo'
        self.assertEqual(isinstance(
            self.auth.is_authenticated(self.request), HttpUnauthorized), True)

        # No api_key.
        self.request.GET['username'] = 'daniel'
        self.assertEqual(isinstance(
            self.auth.is_authenticated(self.request), HttpUnauthorized), True)

        # Wrong user/api_key.
        self.request.GET['username'] = 'daniel'
        self.request.GET['api_key'] = 'foo'
        self.assertEqual(isinstance(
            self.auth.is_authenticated(self.request), HttpUnauthorized), True)

    def test_is_authenticated(self):
        """Should correctly authenticate when using an existing user and key"""
        # Correct user/api_key.
        user = User.objects.get(username='apiuser')
        self.request.GET['username'] = 'apiuser'
        self.request.GET['api_key'] = user.api_key.key
        self.assertEqual(self.auth.is_authenticated(self.request), True)


class ResultBundleTestCase(FixtureTestCase):

    def setUp(self):
        self.data1 = {
            'commitid': '2',
            'branch': 'default', # Always use default for trunk/master/tip
            'project': 'MyProject',
            'executable': 'myexe O3 64bits',
            'benchmark': 'float',
            'environment': "Bulldozer",
            'result_value': 4000,
            }
        DATETIME_FORMAT = '%Y-%m-%d %H:%M:%S'
        self.data_optional = {
            'std_dev': 0.2,
            'val_min': 2.23,
            'val_max': 3.42,
            'date': datetime.now().strftime(DATETIME_FORMAT),
            }
        project_data = dict(
            name="PyPy",
            repo_type="M",
            repo_path="ssh://hg@bitbucket.org/pypy/pypy",
            repo_user="fridolin",
            repo_pass="secret",
            )
        self.project = Project(**project_data)
        self.project.save()
        self.env1 = Environment(name='Bulldozer')
        self.env1.save()

    def test_populate_and_save(self):
        bundle = ResultBundle(**self.data1)
        bundle._populate_obj_by_data()
        # should raise exception if not OK
        bundle.save()
        self.assert_(True)

    def test_save_same_result_again(self):
        """Save a previously saved result. Expected is an IntegrityError
        """
        modified_data = copy.deepcopy(self.data1)
        modified_data['environment'] = "Dual Core"
        bundle = ResultBundle(**modified_data)
        bundle._populate_obj_by_data()
        # FIXME (a8): need to learn how to catch that with assertRaise()
        #self.assertRaises(Exception, bundle.save())
        try:
            bundle.save()
        except IntegrityError:
                self.assertTrue(True, msg="Caught right exception.")
        except Exception as error:
           logging.error('Unexpected exception thrown: {0}'.format(error.__class__,))
        else:
            self.fail('No exception thrown')

    def test_for_nonexistent_environment(self):
        """Save data using non existing environment. Expected is an ImmediateHttpResponse
        """
        modified_data = copy.deepcopy(self.data1)
        modified_data['environment'] = "Foo the Bar"
        #self.assertRaises(ImmediateHttpResponse, bundle._check_data())
        # FIXME (a8): need to learn how to catch that here
        #self.assertRaises(ImmediateHttpResponse, bundle.save())
        try:
            bundle = ResultBundle(**modified_data)
        except ImmediateHttpResponse:
            self.assertTrue(True, msg="Caught right exception.")
        except Exception as error:
            logging.error('Unexpected exception thrown: {0}'.format(error.__class__,))
        else:
            self.fail('No exception thrown')

    def test_insufficient_data(self):
        """See if Result() is saved w/ insufficient data
        """
        modified_data = copy.deepcopy(self.data1)
        modified_data.pop('environment')

        try:
            ResultBundle(**modified_data)
        except ImmediateHttpResponse:
            self.assertTrue(True, msg="Caught right exception.")
        except Exception as error:
            logging.error('Unexpected exception thrown: {0}'.format(error.__class__,))
        else:
            self.fail('No exception thrown')

    def test_date_attr_set(self):
        """
        Check if date attr of Result() is set if not given
        """
        modified_data = copy.deepcopy(self.data1)
        bundle = ResultBundle(**modified_data)
        bundle.save()
        self.assertIsInstance(bundle.obj.date, datetime)
        modified_data['date'] = '2011-05-05T03:01:45'
        #self.assertRaises(ImmediateHttpResponse, ResultBundle(**modified_data))
        try:
            ResultBundle(**modified_data)
        except ImmediateHttpResponse:
            self.assertTrue(True, msg="Caught right exception.")
        except Exception as error:
            logging.error('Unexpected exception thrown: {0}'.format(error.__class__,))
        else:
            self.fail('No exception thrown')

    def test_optional_data(self):
        """
        Check handling of optional data
        """
        data = dict(self.data1.items() + self.data_optional.items())
        bundle = ResultBundle(**data)
        bundle.save()
        self.assertIsInstance(bundle.obj.date, datetime)
        self.assertEqual(bundle.obj.std_dev,
                         float(self.data_optional['std_dev']))
        self.assertEqual(bundle.obj.val_max,
                         float(self.data_optional['val_max']))
        self.assertEqual(bundle.obj.val_min,
                         float(self.data_optional['val_min']))
#def suite():
#    suite = unittest.TestSuite()
#    suite.addTest(EnvironmentTest())
#    return suite
