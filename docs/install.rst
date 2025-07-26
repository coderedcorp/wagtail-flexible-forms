Installation
============

Install from PyPI with:

.. code-block:: console

   $ pip install wagtail-flexible-forms

Be sure to pin the version in your requirements.txt. We recommend pinning the major version, i.e. ``wagtail-flexible-forms==2.*``.

Next, add the app to your Django settings. This ensures that form submissions created from flexible forms will show up in the Wagtail admin.

.. code-block:: python

   INSTALLED_APPS = [
       ...,
       "wagtail_flexible_forms",
       ...,
   ]

Now, you can begin :doc:`adding a form <stream-form>`.
