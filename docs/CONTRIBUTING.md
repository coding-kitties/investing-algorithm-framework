# Contributing to Investing Algorithm Framework

Thank you for considering contributing to the Investing Algorithm Framework! We welcome contributions from the community to make this project better.

Before contributing, please read the [STYLE_GUIDE.md](STYLE_GUIDE.md) to understand the coding style and conventions used in this project. Also, make sure to reach out
to the maintainers in the [Discussions]() or [Issues]() if you have any questions or need help. Also, if you would like to add a new feature or fix a bug, please create first an issue or start a discussion to discuss it with the maintainers.

## How to Contribute

1. **Fork the Repository**: Click the `Fork` button in the top-right corner of the repo.
2. **Clone Your Fork**:

    ```bash
    git clone https://github.com/your-username/your-project.git
    cd your-project
    ```

3. Set Up the Environment: Follow the steps in the README.md to set up dependencies and the local environment.
4. Propose your feature or bugfix in the [issues](https://github.com/coding-kitties/investing-algorithm-framework/issues) or in a [discussion](https://github.com/coding-kitties/investing-algorithm-framework/discussions).
5. Make Changes:
   * Work on your feature or bugfix in a separate branch.
   * Use a meaningful branch name like fix-issue-123 or feature-new-module.
6. Run Tests: Run the tests to ensure your changes don't break anything:

    ```bash
    python -m unittest discover -s tests
    ```

7. Run Linting and make sure your code follows the [style guide](https://github.com/coding-kitties/investing-algorithm-framework):

    ```bash
    flake8 investing_algorithm_framework
    ```

8. Create a Pull Request inline with the [Pull Request Template]().
9. Wait for the maintainers to review your PR. Make changes if requested.
10. Once your PR is approved, it will be merged into the main branch.