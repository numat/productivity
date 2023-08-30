"""Python driver for AutomationDirect Productivity Series PLCs."""
from setuptools import setup

with open('README.md') as in_file:
    long_description = in_file.read()

setup(
    name='productivity',
    version='0.10.1',
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
        'pymodbus>=3.0.2,<3.6.0; python_version >= "3.10"',
        'PyYAML',
    ],
    extras_require={
        'test': [
            'mypy==1.5.1',
            'pytest',
            'pytest-cov',
            'pytest-asyncio',
            'ruff==0.0.286',
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
