import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name="investing_algorithm_framework",
    version="0.0.1",
    description="A framework for creating an investment algorithm",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/investing-algorithms/investing-algorithm-framework.git",
    packages=setuptools.find_packages(exclude=['tests', 'tests.*']),
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: Operating System :: OS Independent",
    ],
    install_requires=[
        'colorama', 'wrapt', 'requests'
    ],
    python_requires='>=3.6',
    scripts=['bin/investing-algorithm-framework-admin'],
    include_package_data=True,
)
