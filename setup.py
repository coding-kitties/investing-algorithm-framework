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
    packages=setuptools.find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires='>=3.6',
    scripts=['investing_bot_framework/bin/investing-bot-admin'],
)