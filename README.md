Wagtail Flexible Forms
======================

Wagtail flexible forms provides a more robust StreamField-based form builder (sometimes called a "StreamForm") with similar functionality to `wagtail.contrib.forms`, plus some extra features including:
* Intermix form fields and content (blocks).
* Multi-step forms.


[Documentation](https://docs.coderedcorp.com/wagtail-flexible-forms/) |
[GitHub](https://github.com/coderedcorp/wagtail-flexible-forms) |
[PyPI](https://pypi.org/project/wagtail-flexible-forms/) |
[Release notes](https://docs.coderedcorp.com/wagtail-flexible-forms/releases.html)


Status
------

[![PyPI - Python Version](https://img.shields.io/pypi/pyversions/wagtail-flexible-forms)](https://pypi.org/project/wagtail-flexible-forms/)
![PyPI - Wagtail Versions](https://img.shields.io/pypi/frameworkversions/wagtail/wagtail-flexible-forms)
[![PyPI - Downloads](https://img.shields.io/pypi/dm/wagtail-flexible-forms)](https://pypi.org/project/wagtail-flexible-forms/)
[![PyPI](https://img.shields.io/pypi/v/wagtail-flexible-forms)](https://pypi.org/project/wagtail-flexible-forms/)


Installation & Usage
--------------------

Read the [documentation](https://docs.coderedcorp.com/wagtail-flexible-forms/), which includes a video demo and example project.


History & Future of This Project
--------------------------------

This project was [originally developed by Bertrand Bordage of NoriPyt](https://www.kickstarter.com/projects/noripyt/wagtails-first-hatch) with the intention of being merged into Wagtail as `wagtail.contrib.stream_forms`.

In 2019, CodeRed used the code as part of Wagtail CRX (`coderedcms`) to and began providing ongoing maintenance as part of that package.

In 2025, with renewed interest from the Wagtail community and the Wagtail core team, CodeRed took ownership of the repository and backported the vendored code from `coderedcms` to produce a stable version of `wagtail-flexible-forms` as its own pip package.

Stay tuned as we work to add more documentation, examples, and unit tests with the goal of eventually merging the package into Wagtail as the official "stream forms" implementation. It is a fantastic package and we are excited to be investing in it to share with the Wagtail community!
