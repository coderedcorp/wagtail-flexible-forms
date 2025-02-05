Contributing
============

To set up your development environment, first create a new virtual environment
(in the ``.venv/`` folder):

(Linux or macOS)

.. code-block:: console

   $ python -m venv .venv
   $ source .venv/bin/activate

(Windows/PowerShell)

.. code-block:: ps1con

   PS> python -m venv .venv
   PS> .venv/Scripts/Activate.ps1

Enter the source code directory and install the package locally with additional
development tools:

.. code-block:: console

   $ pip install -r requirements-dev.txt

Write some code.

Next, run the formatters and static analysis tools:

.. code-block:: console

   $ ruff format .
   $ ruff check --fix .

To build the documentation, run the following, which will output to the
``docs/_build/html/`` directory.

.. code-block:: console

   $ sphinx-build -M html ./docs/ ./docs/_build/ -W

To create a python package, run the following, which will output the package to
the ``dist/`` directory.

.. code-block:: console

   $ python -m build
