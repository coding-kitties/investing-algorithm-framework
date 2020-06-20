# Installation


### Install Python 
Being a Python framework, it requires Python. Python includes a lightweight database called 
SQLite that the framework can use so you won’t need to set up a database just yet.

As of now, the framework only works with python 3.x.
 
### Python pip install (recommended)

You can easily use pip to install the framework in your python environment.

```sh
$ pip install investing-algorithm-framework
```
 
### Installation from source

First clone the repository
```sh
$ git clone https://github.com/investing-algorithms/investing-algorithm-framework.git
```

Then install the framework by running:
```sh
$ pip install <path to cloned investing-algorithm-framework>
```

### Verifying the installation

To verify that you correctly installed the framework, type python from your shell. Then at the Python prompt, 
try to import investing-algorithm-framework:

```python
import investing_algorithm_framework
print(investing_algorithm_framework.get_version())
```
 