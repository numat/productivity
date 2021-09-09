"""Python driver for AutomationDirect Productivity Series PLCs."""
from sys import version_info
from setuptools import setup

if version_info < (3, 6):
    raise ImportError("This module requires Python >=3.6 for asyncio support")
if version_info >= (3, 10):
    raise ImportError("This module depends on pymodbus, which is incompatible with Python 3.10")

with open('README.md', 'r') as in_file:
    long_description = in_file.read()

setup(
    name='productivity',
    version='0.6.0',
    description="Python driver for AutomationDirect Productivity Series PLCs.",
    long_description=long_description,
    long_description_content_type='text/markdown',
    url='http://github.com/numat/productivity/',
    author='Patrick Fuller',
    author_email='pat@numat-tech.com',
    packages=['productivity'],
    entry_points={
        'console_scripts': [('productivity = productivity:command_line')]
    },
    install_requires=[
        'pymodbus>=2.4.0',
        'PyYAML',
    ],
    extras_require={
        'test': [
            'pytest',
            'pytest-cov',
            'pytest-asyncio',
        ],
    },
    license='GPLv2',
    classifiers=[
        'License :: OSI Approved :: GNU General Public License v2 (GPLv2)',
        'Development Status :: 4 - Beta',
        'Natural Language :: English',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
        'Topic :: Scientific/Engineering :: Human Machine Interfaces'
    ]
)
