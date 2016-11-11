import os
from setuptools import find_packages, setup

with open(os.path.join(os.path.dirname(__file__), 'README.rst')) as readme:
    README = readme.read()

# allow setup.py to be run from any path
os.chdir(os.path.normpath(os.path.join(os.path.abspath(__file__), os.pardir)))

setup(
    name='dstack-tasks',
    version='0.10.0',
    packages=find_packages(),
    url='https://github.com/obitec/dstack-tasks',
    license='BSD License',  # example license
    author='JR Minnaar',
    author_email='jr.minnaar@gmail.com',
    description='Collection of tasks to manage the deployment of dockerized django apps.',
    include_package_data=True,
    long_description=README,
    classifiers=[
        'Environment :: Web Environment',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: BSD License',  # example license
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.5',
    ],
    test_suite='nose.collector',
    tests_require=['nose'],
)
