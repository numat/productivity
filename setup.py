"""Python driver for AutomationDirect Productivity Series PLCs."""
from platform import python_version
from setuptools import setup

if python_version() < '3.5':
    raise ImportError("This module requires Python >=3.5")

with open('README.md', 'r') as in_file:
    long_description = in_file.read()

setup(
    name='productivity',
    version='0.3.9',
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
        'pymodbus==2.2.0rc1',
        'PyYAML',
    ],
    license='GPLv2',
    classifiers=[
        'License :: OSI Approved :: GNU General Public License v2 (GPLv2)',
        'Development Status :: 4 - Beta',
        'Natural Language :: English',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
        'Topic :: Scientific/Engineering :: Human Machine Interfaces'
    ]
)
