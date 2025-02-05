from django.db import models
from modelcluster.fields import ParentalKey
from wagtail import blocks
from wagtail.admin.panels import FieldPanel
from wagtail.admin.panels import InlinePanel
from wagtail.contrib.forms.models import AbstractFormField
from wagtail.contrib.forms.models import FormMixin
from wagtail.contrib.forms.models import FormSubmission
from wagtail.fields import RichTextField
from wagtail.fields import StreamField
from wagtail.images.blocks import ImageBlock
from wagtail.models import Page

from wagtail_flexible_forms import blocks as wff_blocks
from wagtail_flexible_forms.models import AbstractSessionFormSubmission
from wagtail_flexible_forms.models import AbstractSubmissionRevision
from wagtail_flexible_forms.models import StreamFormMixin


# -----------------------------------------------------------------------------
# A bare-bones Wagtail page.
# -----------------------------------------------------------------------------


class WagtailPage(Page):
    """
    Normal page that does not include any customization.
    """

    template = "home/page.html"


# -----------------------------------------------------------------------------
# A typical ``wagtail.contrib.forms`` implementation.
# -----------------------------------------------------------------------------


class FormField(AbstractFormField):
    page = ParentalKey(
        "FormPage", on_delete=models.CASCADE, related_name="form_fields"
    )


class FormPage(FormMixin, Page):
    template = "home/form_page.html"
    landing_page_template = "home/form_page_landing.html"

    intro = RichTextField(blank=True)

    content_panels = Page.content_panels + [
        FieldPanel("intro"),
        InlinePanel("form_fields", label="Form fields"),
    ]


# -----------------------------------------------------------------------------
# A ``wagtail_flexible_forms`` implementation.
# -----------------------------------------------------------------------------


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


# Next, let's define temporary objects to hold the submission progress while the
# user fills it out.
class MySubmissionRevision(AbstractSubmissionRevision):
    pass


class MySessionFormSubmission(AbstractSessionFormSubmission):
    @staticmethod
    def get_revision_class():
        return MySubmissionRevision


# Finally, we'll define our Page which pulls it all together.
class SingleStepStreamFormPage(StreamFormMixin, Page):
    template = "home/stream_form_page.html"
    landing_page_template = "home/form_page_landing.html"

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
        Submission class is used to store the final form submission, after
        the user has finished their session.

        For simplicity, let's use Wagtail's default FormSubmission class.
        """
        return FormSubmission

    @staticmethod
    def get_session_submission_class():
        """
        Session submission class is used to stored temporary data while the
        form is being filled out, i.e. for multi-step forms.

        You must return something that inherits from
        ``AbstractSessionFormSubmission``.
        """
        return MySessionFormSubmission


# StreamForms can also have steps, i.e. can be multiple pages with back/next
# buttons. So let's nest our those blocks into a step.
STREAMFORM_STEP_BLOCKS = [
    (
        "sf_step",
        wff_blocks.FormStepBlock(
            [("form_fields", blocks.StreamBlock(STREAMFORM_FIELDS))]
        ),
    )
]


class MultiStepStreamFormPage(StreamFormMixin, Page):
    template = "home/stream_form_page.html"
    landing_page_template = "home/form_page_landing.html"

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
