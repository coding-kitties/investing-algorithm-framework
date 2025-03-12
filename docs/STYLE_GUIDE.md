# Coding agreement

## Purpose of this document

This document sets a baseline to ensure code quality during a project. It provides guidelines on Python coding best practices, but it can be adapted to any other programming language.
You will also find insights on responsibilities expected from a developer / data scientist before opening a Pull Request, and from a reviewer to ensure a good and constructive review.

## Code reviews

[Code reviews](https://microsoft.github.io/code-with-engineering-playbook/code-reviews/inclusion-in-code-review/) are an important part of open source projects. They help ensure the quality of our work and share it with others while proving code quality and sharing understanding.

### Cheat sheets

No matter what your previous experience in a topic is, [anyone can have valuable insights](https://microsoft.github.io/code-with-engineering-playbook/code-reviews/inclusion-in-code-review/#dealing-with-the-impostor-phenomenon)!

Here are below two cheat sheets to follow as a PR author and as PR reviewer.

#### Author cheat sheet

* [Is the size acceptable?](https://microsoft.github.io/code-with-engineering-playbook/code-reviews/pull-requests/#size-guidance)
* [Is it well described?](https://microsoft.github.io/code-with-engineering-playbook/code-reviews/pull-requests/#pull-request-description)
* [Is the check list complete?](https://microsoft.github.io/code-with-engineering-playbook/code-reviews/pull-request-template/pull-request-template/#pr-checklist)
* [Is the language specific guidance respected?](https://microsoft.github.io/code-with-engineering-playbook/code-reviews/recipes/)
* [Are relevant reviewers (if not enforced by policy) added?](https://microsoft.github.io/code-with-engineering-playbook/code-reviews/process-guidance/author-guidance/#add-relevant-reviewers)

Usually, a PR corresponds to a single task, i.e., a unit of added value to the codebase, e.g., a feature, a bugfix, documentation, etc. However, if the PR seems too large or complex, it might be an indicator that a task should be split into multiple pieces and have a PR for each of them.

When a review is conducted, [be open to feedback](https://microsoft.github.io/code-with-engineering-playbook/code-reviews/process-guidance/author-guidance/#be-open-to-receive-feedback).

You can find more detailed guidance as an author on the [ISE Code With Engineering Playbook](https://microsoft.github.io/code-with-engineering-playbook/code-reviews/process-guidance/author-guidance/).

#### Reviewer cheat sheet

* [Understand the code you are reviewing and take your time](https://microsoft.github.io/code-with-engineering-playbook/code-reviews/process-guidance/reviewer-guidance/#general-guidance)
* [Be inclusive, and foster a positive code review culture](https://microsoft.github.io/code-with-engineering-playbook/code-reviews/process-guidance/reviewer-guidance/#foster-a-positive-code-review-culture)
* [Ensure code quality](https://microsoft.github.io/code-with-engineering-playbook/code-reviews/process-guidance/reviewer-guidance/#code-quality-pass)
* Ask for a walkthrough from the author if necessary (do not use walkthrough to hide a PR's complexity, but rather as a way to quickly onboard on it)

You can find more detailed guidance as a reviewer on the [ISE Code With Engineering Playbook](https://microsoft.github.io/code-with-engineering-playbook/code-reviews/process-guidance/reviewer-guidance/).

## Tooling used

Code Quality can be enforced through tools (linters, formatters, type checkers, etc.) that automatically ensure consistency of the code. This topic should be discussed at the beginning of any project to decide which tools are best for your specific project.

Currently, the following tools are recommended:

* Black: code formatter
* Flake8: linter

> Note: We have by default an pipeline that will run flake8 and markdownlint on your PR. You can also run these tools locally to ensure your code is compliant.

## Coding guidelines

This coding agreement provides some guidelines for Python, but they can be adapted to any other programming language.

The guidelines in this section need to be followed by developers / data scientists. Reviewers will also need to validate these guidelines during PR review. The comments in brackets next to the section title refer to production-ready code. Experimental or exploratory code does not need to strictly follow these guidelines. However, it is recommended that most of the rules are followed, because then it will be much easier to convert experimental code into production-ready code when needed.

### Framework project structure [MUST]

The project structure should be organized in a way that is easy to understand and navigate. The structure should be consistent across all projects. Here is an example of a project structure:

```yaml
investing-algorithm-framework/
│
├── investing_algorithm_framework/
│   ├── my_module/
│   │   ├── __init__.py
│   │   └── my_module.py
│   │
│   ├── my_other_module/
│   │   ├── __init__.py
│   │   └── my_other_module.py
│   │
│   └── __init__.py                # Entry point for the application
│
├── tests/
│   ├── test_my_module.py
│   └── test_my_other_module.py
│
├── docs/                      # Documentation (Sphinx, Markdown, etc.)
│
├── .gitignore                 # Ignore unnecessary files
├── README.md                  # Project documentation
├── pyproject.toml           # Build system and tool configurations
└── LICENSE                    # License file
```

### Python Code Layout [MUST]

* `import`: first standard libraries, then third party and finally local libraries. All groups alphabetically sorted.
* `blank lines`: two blank lines surrounding classes and top-level functions. Methods inside functions are surrounded by a single line.
* `indentation`: use 4 spaces (most IDEs will convert tab into 4 spaces by default).
* `line length`: maximum 88 chars.

```python
# Standard libs
import std_lib_1
import std_lib_2

# Third party libs
import third_party_lib_1
import third_party_lib_2

# Local lib
from local_lib import class_1, function_1


# After two blank lines
def top_level_function(args: int) -> str:
    # Body
```

### Python Naming convention [MUST]

* File names: lowercase, words separated by an underscore, e.g., `my_file.py`.

* `language, spelling`:
  * Class names, function names, and variable names are written in English. Use meaningful and grammatically correct names.
  * Use verbs to name functions and methods (they are actions), and names to name variables and classes (they are things).
* `class name`: name should start with an uppercase and follow the camlCase convention if it has more than two words.
* `function name`:
  * lowercase, words separated by an underscore.
  * add `self` argument at first position if the method is a class's method.
  * if the function's name clashes with a reserved word, append underscore.
  * use 2 underscores at the beginning for private class's methods.
  * use 1 underscore at the beginning of a private field.
  * specify the type of your input parameters
  * always provide a return type (use 'None' if 'void').
* `variable name`: lowercase, words separated by an underscore.
* `constant name`: uppercase, words separated by an underscore.

```python
my_variable = 10

GLOBAL_CONSTANT = 10

class CatalogInformation:
    def __init__(self, name: str) -> None:
        # Body constructor

    def get_metadata_count(self) -> int:
        # Body method
        return 1

    def __check_internal_property(self) -> bool:
        # Body private method
        return True
```

### Python Comments / documentation [MUST]

Use comments, provide explanation on complex algorithms. Unless a function is trivial, always add a high-level comment.

Use docstrings to document your code. Docstrings are used to document the purpose of a function, the parameters it takes, and the return value. They are used to generate documentation automatically. [Google-style docstrings](https://sphinxcontrib-napoleon.readthedocs.io/en/latest/example_google.html) are recommended.

```python
def is_valid(a: int, b: str) -> bool:
    """
    Explanation of the function

    Args:
        a (int): The first number.
        b (int): The second number.

    Returns:
        Type: The return type.
    """
```

### Python Tuples, Lists, Dictionaries [MUST]

Use tuples when data is non-changeable, dictionaries when you need to map things, and lists if your data can change later.

Functions can return multiple values, no need for a list:

```python
def get_info(self) -> str, int:
    """
    Return a string and an integer

    Args:
        - str: a string
        - int: an integer
    """
    return "hello world", 30
```

### Python Use context managers [MUST]

Context managers are tool to use in situations where you need to run some code that has preconditions and postconditions.

For instance, when you read the content of a file, you need to ensure that you close the handle regardless of the success or the failure of the operation. With the `with` keyword you can achieve this:

```python
with open(filename) as fd:
    process_file(fd)

# Note that parentheses are supported in Python 3.10 for context manager,
# useful when you have many 'with'
with (
    CtxManager1() as example1,
    CtxManager2() as example2,
    CtxManager3() as example3,
):
    ...
```

You can implement your own context manager should you need to execute actions in a certain order. Consider the case where you want to update a service configuration. You need first to stop the service, update the configuration then start the service again:

```python
class ServiceHandler:
    def __enter__(self) -> ServiceHandler:
        run("systemctl stop my.service")
        return self

    def __exit__(self, exc_type: str, ex_value: str, ex_traceback: str) -> None:
        run("systemctl start my.service")

def update_service_conf() -> None:
    # Body to update service's configuration

if __name__ == '__main__':
    with ServiceHandler():
        update_service_conf()
```

### Python Exceptions handling [MUST]

Hiding an exception or not properly anticipating potential errors (accessing an API for instance, network issues *can* arise) can lead to unexpected behaviors or terminating the execution. Another example is that the caller should be notified if a function receives wrong input parameters to avoid this way wrong results that might be difficult to debug.

Each function has a logic, this logic must be followed by exceptions raised. For instance, if you have a function that get some data from an API, exceptions raised by this function should be logical: connection error, timeout etc. The exception must be raised at the right level of abstraction.

If you choose to propagate the exception to the caller, ensure that you do not expose sensitive information. Tracebacks of exceptions can contain sensitive details leading to exposing intellectual property.

Do not use exceptions as a `go-to` logic, meaning catching an exception and from the `except` calling other business code - the flow of the program will become harder to read. Exceptions are *usually* to notify the caller that something unexpected occured.

Finally, [observability](https://microsoft.github.io/code-with-engineering-playbook/observability/) is an important engineering fundamental. Properly handling exceptions and managing observability (with AppInsight for instance) will lead to a more robust application and easier debugging when something unexpected occurs.

```python
# Never do ...
try:
    process_data()
except:
    pass

# Encapsulate orginal exception trace
def process_data() -> None:
    try:
        do_something()
    except KeyError as e:
        # Raise a specific exception from do_something,
        # encapsulate trace to a custom exception
        raise MyApplicationException("Item not present") from e
```

### Unit tests [MUST]

Unit testing is a core tool in software engineering. They help us verify the correctness of our code, encourage good design practices, and reduce chances to have bugs hitting production. Unit tests can improve development efficiency.

Unit tests should be:

* Reliable: should be 100% reliable so failures indicate a bug in the code.
* Fast: should run in milliseconds.
* Isolated: removing all external dependencies ensures reliability and speed.

#### Python unit tests

For Python, we recommend using `unittest`. `unittest` is a powerful tool that makes it easy to write simple tests, but also scales to support complex functional testing for applications and libraries.

```python
from unittest import TestCase


class TestMyClass(TestCase):

    def setup(self):
        # Setup

    @classmethod
    def setup_class(cls):
        # Setup class
        pass

    def test_my_function(self):
        # Test the function
        self.assertEqual(my_function(1), 2)
```

Please refer to [unittest site](https://docs.python.org/3/library/unittest.html) for more useful patterns.
