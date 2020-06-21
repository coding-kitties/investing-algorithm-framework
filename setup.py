import setuptools

VERSION = "0.1"
with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name="investing_algorithm_framework",
    version=VERSION,
    license="BSL-1.1",
    author="coding kitties",
    description="A framework for creating an investment algorithm",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/investing-algorithms/investing-algorithm-framework.git",
    download_url='https://github.com/investing-algorithms/investing-algorithm-framework/archive/v0.1.tar.gz',
    packages=setuptools.find_packages(exclude=['tests', 'tests.*']),
    keywords=['INVESTING', 'BOT', 'ALGORITHM', 'FRAMEWORK'],
    classifiers=[
        "Intended Audience :: Developers",
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.4',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
        "Topic :: Software Development",
        "License :: Other/Proprietary License",
    ],
    install_requires=[
        'colorama', 'wrapt', 'requests', 'SQLAlchemy', 'pytest'
    ],
    python_requires='>=3.6',
    scripts=['bin/investing-algorithm-framework-admin'],
    include_package_data=True,
)
