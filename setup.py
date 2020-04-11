import setuptools
import sys

if sys.version_info[0] < 3:
    sys.exit('Python < 3 is unsupported.')


import shournal_to_snakemake
from shournal_to_snakemake import app

with open("README.md", "r") as fh:
    long_description = fh.read()

requirements = ['ordered-set', ]

packages = ['shournal_to_snakemake']
for p in setuptools.find_packages('shournal_to_snakemake'):
    packages.append("{}/{}".format(app.APP_NAME, p))

setuptools.setup(
    name=app.APP_NAME,
    version=shournal_to_snakemake.__version__,
    author=shournal_to_snakemake.__author__,
    author_email="tychokirchner@mail.de",
    description="Transform a command series from shournal into Snakemake rules",
    long_description=long_description,
    url="https://github.com/snakemake/shournal-to-snakemake",
    packages=packages,
    license='MIT',
    install_requires=requirements,

    command_options={
        'build_sphinx': {
            'project': ('setup.py', app.APP_NAME),
            'version': ('setup.py', shournal_to_snakemake.__version__),
            'release': ('setup.py', shournal_to_snakemake.__version__),
            'source_dir': ('setup.py', 'doc')}},

entry_points={
        'console_scripts': [
            'shournal-to-snakemake = shournal_to_snakemake.__main__:main',
        ],
    },
    classifiers=[
        'Environment :: Console',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3',
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
)
