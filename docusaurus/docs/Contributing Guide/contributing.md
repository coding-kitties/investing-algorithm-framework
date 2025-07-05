---
id: contributing
title: Contributing to Investing Algorithm Framework
sidebar_label: Contributing
---

# Contributing to Investing Algorithm Framework

Thank you for considering contributing to the Investing Algorithm Framework! We welcome contributions from the community to make this project better.

Before contributing, please read the [STYLE_GUIDE.md](style_guide.md) to understand the coding style and conventions used in this project. Also, make sure to reach out
to the maintainers in the [Discussions](https://github.com/coding-kitties/investing-algorithm-framework/discussions) or [Issues](https://github.com/coding-kitties/investing-algorithm-framework/issues) if you have any questions or need help. Also, if you would like to add a new feature or fix a bug, please create first an issue or start a discussion to discuss it with the maintainers.

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

8. Create a Pull Request inline with the [Pull Request Template](https://github.com/coding-kitties/investing-algorithm-framework/blob/main/docs/PULL_REQUEST_TEMPLATE.md).
9. Wait for the maintainers to review your PR. Make changes if requested.
10. Once your PR is approved, it will be merged into the main branch.

## Architecture Overview

### Onion layered architecture

The Investing Algorithm Framework follows an Onion Architecture pattern, which promotes separation of concerns and testability. The core of the architecture consists of:
- **Domain Layer**: Contains the core business logic and domain entities. This layer is independent of any external frameworks or libraries.
- **Application Layer**: Contains application services that orchestrate the domain logic. It interacts with the domain layer and provides a clean API for the outer layers.
- **Infrastructure Layer**: Contains implementations of external services, such as data sources, APIs, and other integrations. This layer depends on the application layer but not the other way around.
- **Service layer**: Contains the service classes that provide a higher-level API for the application layer. It is responsible for coordinating the interactions between the application layer and the infrastructure layer.

The architecture looks as follows:

```bash
- investing_algorithm_framework
  ├── domain
  │   ├── models
  │   ├── metrics
  │   ├── exceptions
  │   ├── constants  
  │   └── interfaces
  ├── services
  │   ├── services
  │   └── use_cases
  ├── infrastructure
  │   ├── data_sources
  │   └── external_services
  ├── APP
  │   ├── app.py
  │   ├── config.py
  |   └── logger.py
  └── service_layer
```

### Dataframes
The framework relies heavily on dataframe operations and supports both Pandas and Polars. However, internally we always use Polars dataframes for performance reasons.
Therefore, if a dataframe is passed as a parameter to a function, you can safely assume that it's a polars dataframe.

Polars is generally faster than Pandas for handling datetime operations — especially on large datasets — due to:
* Its Rust-based backend (highly optimized)
* Better multi-threaded execution
* More efficient memory handling

#### Datetime handling
Each timeseries dataframe will have its Datetime column timezone set to UTC. This is done to ensure consistency across different data sources 
and to avoid issues with timezone conversions. When working with datetime columns, always ensure that you are aware of the timezone and convert it to UTC if necessary.

Also, it's often the case the exchanges and brokers use UTC as the timezone for their data. For example, The CCXT documentation clearly states:

> Timestamps returned by fetchOHLCV() and other market data methods are in milliseconds since Epoch in UTC.
