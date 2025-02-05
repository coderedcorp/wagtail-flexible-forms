Stream Form with Steps
======================

Multi-step forms enable you to break your form up into separate "pages" which the user can navigate forwards and backwards as they fill out their form.

This tutorial assumes you have already added the code from :doc:`stream-form`.


Step 1: Define Step Blocks
--------------------------

In addition to the ``STREAMFORM_FIELDS`` we defined previously, let's add those fields into a step block.

In ``home/models.py``:

.. code-block:: python

   from wagtail_flexible_forms import blocks as wff_blocks

   STREAMFORM_STEP_BLOCKS = [
       (
           "sf_step",
           wff_blocks.FormStepBlock(
               [("form_fields", STREAMFORM_FIELDS)]
           ),
       )
   ]


Step 2: Define a Stream Form Page with Steps
--------------------------------------------

.. code-block:: python

   from wagtail.admin.panels import FieldPanel
   from wagtail.contrib.forms.models import FormSubmission
   from wagtail.fields import RichTextField
   from wagtail.fields import StreamField
   from wagtail.models import Page
   from wagtail_flexible_forms.models import StreamFormMixin

   class StreamFormStepPage(StreamFormMixin, Page):
       template = "home/stream_form_page.html"
       landing_page_template = "home/form_page_landing.html"

       # Typical Wagtail field, like any other page.
       intro = RichTextField(blank=True)

       # Set ``form_fields`` to contain our multi-step fields.
       form_fields = StreamField(STREAMFORM_STEP_BLOCKS)

       content_panels = Page.content_panels + [
           FieldPanel("intro"),
           FieldPanel("form_fields"),
       ]

       @staticmethod
       def get_submission_class():
           return FormSubmission

       @staticmethod
       def get_session_submission_class():
           return MySessionFormSubmission


Step 3: Create HTML Templates
-----------------------------

More robust templates are available in the `testproject <https://github.com/coderedcorp/wagtail-flexible-forms/tree/main/testproject>`_, however the examples below will get you started.

Modify our page template to included step info, and previous/next buttons.

File: ``home/templates/home/stream_form_page.html``

.. code:: html+django

   {% load static wagtailcore_tags %}
   <html>
     <head>
       <title>{{ page.title }}</title>
     </head>
     <body>

       <h1>{{ page.title }}</h1>

       {{ page.intro | richtext }}

       <!-- Show step info -->
       <h2>{{step.name}}</h2>
       {% with last_step=steps|last %}
       <p>Step {{step.index|add:"1"}} of {{last_step.index|add:"1"}}</p>
       {% endwith %}
       <hr>

       <form action="{% pageurl self %}" method="POST" enctype="{{ form_enctype }}">
         {% csrf_token %}

         {% for item in markups_and_bound_fields %}
         <!-- render content blocks -->
         {% if item.type == "markup" %}
         {% include_block item.block %}
         <!-- render form fields -->
         {% elif item.type == "field" %}
         <div class="field">
           {{ item.field.errors }}
           {{ item.field.label_tag }} {{ item.field }}
         </div>
         {% endif %}
         {% endfor %}

         <!-- Show previous/next buttons -->
         {% if step != steps|first %}
         <a href="{{page.url}}?step={{step.index}}">
            Previous
         </a>
         {% endif %}
         <button type="submit">
           {% if steps|last == step %}Submit{% else %}Next{% endif %}
         </button>

       </form>
     </body>
   </html>


Step 4: Migrate
---------------

Finally, you'll need to make and run migrations. Then, begin editing your new page in the Wagtail admin.

.. code-block:: console

   $ python manage.py makemigrations
   $ python manage.py migrate
