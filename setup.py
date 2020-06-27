from setuptools import setup

with open('README.rst', 'r') as f:
    long_description = f.read()

setup(
    name='dstack-tasks',
    version='2.3.4',
    description=(
        "CLI that accompanies dstack-tasks make it easy to build and deploy application. "
        "Integrates with dstack-factory."),
    long_description=long_description,
    url='https://github.com/obitec/dstack-tasks',
    author='J Minnaar',
    author_email='jr.minnaar@gmail.com',
    license='MIT License',
    keywords='docker python wheels images runtime automation deploy',
    classifiers=[
        'Development Status :: 5 - Production/Stable',
        'Intended Audience :: System Administrators',
        'Topic :: Software Development :: Build Tools',
        'Topic :: System :: Installation/Setup',
        'Topic :: System :: Software Distribution',
        'Operating System :: OS Independent',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
    ],
    packages=['dstack_tasks', ],
    include_package_data=True,
    zip_safe=True,
    install_requires=[
        'awscli',
        'boto3',
        'colorama',
        'fabric',
        'invoke',
        'python-dotenv',
        'requests',
    ],
    extras_require={'dev': ['twine', 'wheel']},
    entry_points={'console_scripts': ['dstack = dstack_tasks.main:program.run']},
)
