import setuptools
from version import get_version

VERSION = get_version()

with open("README.md", "r") as fh:
    long_description = fh.read()

with open('requirements.txt') as f:
    required = f.read().splitlines()

setuptools.setup(
    name="investing_algorithm_framework",
    version=get_version(),
    license='Apache License 2.0',
    author="coding kitties",
    description="A framework for creating an investment algorithm",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/coding-kitties/investing-algorithm-framework.git",
    download_url='https://github.com/coding-kitties/investing-algorithm-framework/archive/v0.1.1.tar.gz',
    packages=setuptools.find_packages(
        exclude=['tests', 'tests.*', 'examples', 'examples.*']
    ),
    keywords=['TRADING', 'INVESTING', 'BOT', 'ALGORITHM', 'FRAMEWORK'],
    classifiers=[
        "Intended Audience :: Developers",
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.4',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
        "Topic :: Software Development",
        'License :: OSI Approved :: Apache Software License',
        'Operating System :: OS Independent',
    ],
    install_requires=required,
    python_requires='>=3',
    include_package_data=True,
)
