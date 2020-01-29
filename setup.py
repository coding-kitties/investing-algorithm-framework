import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name="investing_bot_framework",
    version="0.0.1",
    author="Marc van Duyn",
    author_email="marcvanduyn@gmail.com",
    description="A framework for creating an investment bot",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/pypa/sampleproject",
    packages=setuptools.find_packages(exclude=['tests', 'tests.*']),
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: Operating System :: OS Independent",
    ],
    python_requires='>=3.6',
    scripts=['bot/bin/investing-bot-admin'],
    include_package_data=True,
)
