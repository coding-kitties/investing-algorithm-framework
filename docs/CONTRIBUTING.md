# Contributing

## Contribute to the value investing bot

Feel like the framework is missing a feature or can be fixed? We welcome your pull requests! 

Few pointers for contributions:

- Create your branch against the `develop` branch, not `master`.
- New features need to contain unit tests and must be PEP8 conformant (max-line-length = 100).
- Creating a feature, must be done on a branch with prefix `feature_`.
- Making a hotfix, must be done on a branch with prefix `hotfix_`.

If you are unsure, discuss the feature or hotfix on our [Slack](https://inv-algo-framework.slack.com)
or in a [issue](https://github.com/investingbots/value-investing-bot/issues) before a PR.

## Rules

### 1. Run unit tests

All unit tests must pass. If a unit test is broken, change your code to 
make it pass. It means you have introduced a regression.

#### Test the whole project

```bash
pytest
```

#### Test only one file

```bash
pytest tests/test_<file_name>.py
```

#### Test only one method from one file

```bash
pytest tests/test_<file_name>.py::test_<method_name>
```

### 2. Test if your code is PEP8 compliant

#### Run Flake8

```bash
flake8 investing_algorithm_framework
```

### 3. Test if all type-hints are correct

#### Run mypy

``` bash
mypy investing_algorithm_framework
```

### Process: Your own code changes

All code changes, regardless of who does them, need to be reviewed and merged by someone else.
This rule applies to all the core committers.

### Responsibilities

- Ensure cross-platform compatibility for every change that's accepted. Windows, Mac & Linux.
- Ensure no malicious code is introduced into the core code.
- Create issues for any major changes and enhancements that you wish to make. Discuss things transparently and get community feedback.
- Keep feature versions as small as possible, preferably one new feature per version.
- Be welcoming to newcomers and encourage diverse new contributors from all backgrounds. See the Python Community Code of Conduct (https://www.python.org/psf/codeofconduct/).

### Becoming a Committer

Contributors may be given commit privileges. Preference will be given to those with:

1. Past contributions to value investing algorithm framework and other related open-source projects. 
Contributions to value for the framework include both code (both accepted and pending) and friendly participation in the issue tracker and Pull request reviews. Quantity and quality are considered.
1. A coding style that the other core committers find simple, minimal, and clean.
1. Access to resources for cross-platform development and testing.
1. Time to devote to the project regularly.

Being a Committer does not grant write permission on `develop` or `master` for security reasons (Users trust the investing algorithm framework with their financial secrets).

### Help

If you want help, or not sure on how to become a committer for the project, feel free to sent an email to: investing.algorithm.framework@gmail.com