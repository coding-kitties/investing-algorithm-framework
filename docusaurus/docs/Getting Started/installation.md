---
sidebar_position: 1
---

# Installation

Get started with the Investing Algorithm Framework by following these simple installation steps.

## Prerequisites

Before installing the framework, ensure you have:

- **Python 3.10+** installed on your system
- **pip** (Python package installer)
- **git** (for cloning repositories)

## Installation Options

### Option 1: Install from PyPI (Recommended)

Install the latest stable version from PyPI:

```bash
pip install investing-algorithm-framework
```

This installs the core framework with [CCXT](https://github.com/ccxt/ccxt) support.

### Optional Data Provider Extras

The framework supports additional data providers that can be installed as optional extras:

```bash
# Yahoo Finance (stocks, ETFs, indices — free, no API key)
pip install investing-algorithm-framework[yahoo]

# Alpha Vantage (stocks, forex, crypto — free API key required)
pip install investing-algorithm-framework[alpha_vantage]

# Polygon.io (US stocks, options, forex, crypto — API key required)
pip install investing-algorithm-framework[polygon]

# Install all optional data providers at once
pip install investing-algorithm-framework[all]
```

You can combine multiple extras:

```bash
pip install investing-algorithm-framework[yahoo,polygon]
```

### Cloud Deployment Extras

If you plan to deploy your bot to AWS Lambda or Azure Functions (see [How to deploy a trading bot](deployment)), install the extra matching your target platform. These pull in the SDKs needed for the corresponding `StateHandler` (e.g. `AWSS3StorageStateHandler`, `AzureBlobStorageStateHandler`) and the `iaf deploy-*` CLI commands:

```bash
# AWS Lambda (S3-backed state storage)
pip install investing-algorithm-framework[aws]

# Azure Functions (Blob Storage-backed state storage)
pip install investing-algorithm-framework[azure]
```

These can also be combined with data provider extras, e.g. `investing-algorithm-framework[aws,yahoo]`.

### Option 2: Install from Source

For the latest development version, install directly from GitHub:

```bash
pip install git+https://github.com/coding-kitties/investing-algorithm-framework.git
```

### Option 3: Development Installation

If you plan to contribute to the framework:

1. **Clone the repository:**
   ```bash
   git clone https://github.com/coding-kitties/investing-algorithm-framework.git
   cd investing-algorithm-framework
   ```

2. **Install in development mode:**
   ```bash
   pip install -e .
   ```

## Next Steps

Once installation is complete, proceed to [Application Setup](application-setup) to create your first trading application!
