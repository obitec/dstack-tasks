import os
from setuptools import find_packages, setup

with open(os.path.join(os.path.dirname(__file__), 'README.rst')) as readme:
    README = readme.read()

# allow setup.py to be run from any path
os.chdir(os.path.normpath(os.path.join(os.path.abspath(__file__), os.pardir)))

setup(
    name='dstack-tasks',
    version='1.0.0',
    packages=find_packages(),
    url='https://github.com/obitec/dstack-tasks',
    license='BSD License',  # example license
    author='JR Minnaar',
    author_email='jr.minnaar+pypi@gmail.com',
    description='Collection of tasks to manage the deployment of dockerized django apps.',
    include_package_data=True,
    long_description=README,
    classifiers=[
        'Environment :: Web Environment',
        'Development Status :: 4 - Beta',
        'Intended Audience :: System Administrators',
        'License :: OSI Approved :: BSD License',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
    ],
    install_requires=[
        'Fabric3>=1.12.post1',
        'python-dotenv>=0.5.1',
        'pyyaml>=3.11',
        'setuptools_scm',
    ],
    extras_require={
        'dev': [
            'invoke>=0.13.0',
            'Sphinx>=1.4.1',
            'wheel>=0.29.0',
        ],
        'test': ['coverage'],
    },
    test_suite='nose.collector',
    tests_require=['nose'],
)
