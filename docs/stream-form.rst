Adding a Stream Form
====================

Stream Forms behave similar to the Wagtail Form Builder, and are just like any other Wagtail Page. The difference is: the form fields are defined in a ``StreamField``. Because they are in a ``StreamField``, **any** blocks can be mixed and matched together to give your editors exactly what they need.

In this tutorial, assume that your Django app is named ``home``.


Step 1: Define Blocks
---------------------

In ``home/models.py``, let's first define some blocks:

.. code-block:: python

   from wagtail import blocks
   from wagtail.images.blocks import ImageBlock
   from wagtail_flexible_forms import blocks as wff_blocks

   # First, let's define the fields we'd like our form to contain, as blocks.
   # StreamForms can contain *any* block, not just form fields!
   STREAMFORM_FIELDS = [
       # Include form field blocks from wagtail_flexible_forms.
       ("sf_singleline", wff_blocks.CharFieldBlock(group="Fields")),
       ("sf_multiline", wff_blocks.TextFieldBlock(group="Fields")),
       ("sf_checkboxes", wff_blocks.CheckboxesFieldBlock(group="Fields")),
       ("sf_radios", wff_blocks.RadioButtonsFieldBlock(group="Fields")),
       ("sf_dropdown", wff_blocks.DropdownFieldBlock(group="Fields")),
       ("sf_checkbox", wff_blocks.CheckboxFieldBlock(group="Fields")),
       ("sf_date", wff_blocks.DateFieldBlock(group="Fields")),
       ("sf_time", wff_blocks.TimeFieldBlock(group="Fields")),
       ("sf_datetime", wff_blocks.DateTimeFieldBlock(group="Fields")),
       ("sf_image", wff_blocks.ImageFieldBlock(group="Fields")),
       ("sf_file", wff_blocks.FileFieldBlock(group="Fields")),
       # And content blocks from Wagtail!
       ("text", blocks.RichTextBlock(group="Content")),
       ("image", ImageBlock(group="Content")),
   ]


Step 2: Define Form Submissions
-------------------------------

Since Stream Forms can have multiple steps (more on that later) they need a temporary session-based model to store the data as the user fills out the form. The default implementation is to delete them at the end, and create a finalized form submission similar to Wagtail contrib forms.

.. code-block:: python

   from wagtail_flexible_forms.models import AbstractSessionFormSubmission
   from wagtail_flexible_forms.models import AbstractSubmissionRevision

   class MySubmissionRevision(AbstractSubmissionRevision):
       pass

   class MySessionFormSubmission(AbstractSessionFormSubmission):
       @staticmethod
       def get_revision_class():
           return MySubmissionRevision


Step 3: Define a Stream Form Page
---------------------------------

.. code-block:: python

   from wagtail.admin.panels import FieldPanel
   from wagtail.contrib.forms.models import FormSubmission
   from wagtail.fields import RichTextField
   from wagtail.fields import StreamField
   from wagtail.models import Page
   from wagtail_flexible_forms.models import StreamFormMixin

   class StreamFormPage(StreamFormMixin, Page):
       template = "home/stream_form_page.html"
       landing_page_template = "home/form_page_landing.html"

       # Typical Wagtail field, like any other page.
       intro = RichTextField(blank=True)

       # Set ``form_fields`` to contain our Streamform fields.
       form_fields = StreamField(STREAMFORM_FIELDS)

       content_panels = Page.content_panels + [
           FieldPanel("intro"),
           FieldPanel("form_fields"),
       ]

       @staticmethod
       def get_submission_class():
           """
           Submission class is used to store the final form
           submission, after the user has finished their session.

           For simplicity, use Wagtail's default FormSubmission class.
           """
           return FormSubmission

       @staticmethod
       def get_session_submission_class():
           """
           Session submission class is used to store temporary
           data while the form is being filled out, i.e. for
           multi-step forms.

           You must return something that inherits from
           ``AbstractSessionFormSubmission``.
           """
           return MySessionFormSubmission


Step 4: Create HTML Templates
-----------------------------

More robust templates are available in the `testproject <https://github.com/coderedcorp/wagtail-flexible-forms/tree/main/testproject>`_, however the examples below will get you started.

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

         <button type="submit">Submit</button>

       </form>
     </body>
   </html>

File: ``home/templates/home/form_page_landing.html``

.. code:: html+django

   {% load static wagtailcore_tags %}
   <html>
     <head>
       <title>{{ page.title }}</title>
     </head>
     <body>

       <h1>{{ page.title }}</h1>

       <h2>Thank you.</h2>
       <p>We have received your submission!</p>

     </body>
   </html>


Step 5: Migrate
---------------

Finally, you'll need to make and run migrations. Then, begin editing your new page in the Wagtail admin.

.. code-block:: console

   $ python manage.py makemigrations
   $ python manage.py migrate
