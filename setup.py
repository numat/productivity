"""Python driver for AutomationDirect Productivity Series PLCs."""
from sys import version_info

from setuptools import setup

if version_info < (3, 7):
    raise ImportError("This module requires Python >=3.7.  Use 0.6.0 for Python3.6")

with open('README.md') as in_file:
    long_description = in_file.read()

setup(
    name='productivity',
    version='0.9.2',
    description="Python driver for AutomationDirect Productivity Series PLCs.",
    long_description=long_description,
    long_description_content_type='text/markdown',
    url='https://github.com/numat/productivity/',
    author='Patrick Fuller',
    author_email='pat@numat-tech.com',
    maintainer="Alex Ruddick",
    maintainer_email="alex@numat-tech.com",
    packages=['productivity'],
    entry_points={
        'console_scripts': [('productivity = productivity:command_line')]
    },
    install_requires=[
        'pymodbus>=2.4.0; python_version == "3.8"',
        'pymodbus>=2.4.0; python_version == "3.9"',
        'pymodbus>=3.0.2,<3.4.0; python_version >= "3.10"',
        'PyYAML',
    ],
    extras_require={
        'test': [
            'mypy==1.4.1',
            'pytest',
            'pytest-cov',
            'pytest-asyncio',
            'ruff==0.0.275',
            'types-PyYAML'
        ],
    },
    license='GPLv2',
    classifiers=[
        'License :: OSI Approved :: GNU General Public License v2 (GPLv2)',
        'Development Status :: 4 - Beta',
        'Natural Language :: English',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
        'Programming Language :: Python :: 3.10',
        'Programming Language :: Python :: 3.11',
        'Topic :: Scientific/Engineering :: Human Machine Interfaces'
    ]
)
