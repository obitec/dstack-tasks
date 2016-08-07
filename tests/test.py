from unittest import TestCase

from dstack_tasks import *


class TestVC(TestCase):
    def test_vc_returns_string(self):
        tag = vc(release_tag='v0.9.9', release_type='patch')
        self.assertTrue(isinstance(tag, str))

    def test_vc_patch(self):
        self.assertEqual(vc(release_tag='v0.9.9', release_type='patch'), 'v0.9.10')

    def test_vc_minor(self):
        self.assertEqual(vc(release_tag='v0.9.9', release_type='minor'), 'v0.10.0')

    def test_vc_major(self):
        self.assertEqual(vc(release_tag='v0.9.9', release_type='major'), 'v1.0.0')


class TestDirify(TestCase):
    def test_dirify_returns_str(self):
        tmp_dir = dirify(base_path='/tmp')
        self.assertTrue(isinstance(tmp_dir('run'), str))

    def test_dirify_subdir(self):
        tmp_dir = dirify(base_path='/tmp')
        self.assertEqual(tmp_dir('run'), '/tmp/run')

    def test_empty_subdir(self):
        tmp_dir = dirify(base_path='/tmp')
        self.assertEqual(tmp_dir(''), '/tmp')

