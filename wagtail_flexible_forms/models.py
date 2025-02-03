import datetime
import json
import typing
from collections import OrderedDict
from collections import namedtuple
from importlib import import_module
from itertools import zip_longest
from pathlib import Path

from django import forms
from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.core.files.storage import default_storage
from django.core.serializers.json import DjangoJSONEncoder
from django.db import models
from django.db.models.fields.files import FieldFile
from django.db.models.signals import post_delete
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.http import HttpResponseRedirect
from django.template.response import TemplateResponse
from django.utils.safestring import SafeData
from django.utils.safestring import mark_safe
from django.utils.translation import gettext_lazy as _
from wagtail.contrib.forms.models import AbstractEmailForm
from wagtail.contrib.forms.models import AbstractForm
from wagtail.contrib.forms.models import AbstractFormSubmission
from wagtail.contrib.forms.models import FormSubmission
from wagtail.contrib.forms.views import SubmissionsListView

from .blocks import FormFieldBlock
from .blocks import FormStepBlock


Element = namedtuple("Element", ["type", "block", "field"])
"""
A simple "object" to hold rendered values from the streamfield.
"""


def get_form_enctype(form: forms.Form):
    """
    Utility to check if a Django form contains a file field and return the
    appropriate ``enctype`` attribute for an HTML ``<form>``.
    """
    for field in form:
        if isinstance(field.field.widget, forms.ClearableFileInput):
            return "multipart/form-data"
    return "application/x-www-form-urlencoded"


class Step:
    def __init__(self, steps, index, struct_child):
        self.steps = steps
        self.index = index
        block = getattr(struct_child, "block", None)
        if isinstance(block, FormStepBlock):
            self.name = struct_child.value["name"]
            self.form_fields = struct_child.value["form_fields"]
        else:
            self.name = ""
            self.form_fields = struct_child

    @property
    def index1(self):
        return self.index + 1

    @property
    def url(self):
        return "%s?step=%s" % (self.steps.page.url, self.index1)

    def get_form_fields(self):
        form_fields = OrderedDict()
        field_blocks = self.form_fields
        for struct_child in field_blocks:
            block = struct_child.block
            if isinstance(block, FormFieldBlock):
                struct_value = struct_child.value
                field_name = block.get_slug(struct_value)
                form_fields[field_name] = block.get_field(struct_value)
        return form_fields

    def get_form_class(self):
        return type(
            "WagtailForm",
            self.steps.page.get_form_class_bases(),
            self.get_form_fields(),
        )

    def get_markups_and_bound_fields(self, form):
        """
        Yields ``Element`` tuples of:
        0: Type indicator of "field" or "markup".
        1: The Wagtail block object.
        2: Field name (or None for non-fields i.e. markup).
        """
        for struct_child in self.form_fields:
            block = struct_child.block
            if isinstance(block, FormFieldBlock):
                struct_value = struct_child.value
                field_name = block.get_slug(struct_value)
                yield Element("field", struct_child, form[field_name])
            else:
                yield Element("markup", struct_child, None)

    def __str__(self):
        if self.name:
            return self.name
        return _("Step %s") % self.index1

    @property
    def badge(self):
        return mark_safe('<span class="badge">%s/%s</span>') % (
            self.index1,
            len(self.steps),
        )

    def __html__(self):
        return "%s %s" % (self, self.badge)

    @property
    def is_active(self):
        return self.index == self.steps.current_index

    @property
    def is_last(self):
        return self.index1 == len(self.steps)

    @property
    def has_prev(self):
        return self.index > 0

    @property
    def has_next(self):
        return self.index1 < len(self.steps)

    @property
    def prev(self):
        if self.has_prev:
            return self.steps[self.index - 1]

    @property
    def next(self):
        if self.has_next:
            return self.steps[self.index + 1]

    def get_existing_data(self, raw=False):
        data = self.steps.get_existing_data()[self.index]
        fields = self.get_form_fields()
        if not raw:

            class FakeField:
                storage = self.steps.get_storage()

            for field_name, value in data.items():
                if field_name in fields and isinstance(
                    fields[field_name], forms.FileField
                ):
                    data[field_name] = FieldFile(None, FakeField, value)
        return data

    @property
    def is_available(self):
        return self.prev is None or self.prev.get_existing_data(raw=True)


class StreamFormJSONEncoder(DjangoJSONEncoder):
    def default(self, o):
        try:
            from phonenumber_field.phonenumber import PhoneNumber
        except ImportError:
            pass
        else:
            if isinstance(o, PhoneNumber):
                return str(o)

        return super().default(o)


class Steps(list):
    def __init__(self, page, request=None):
        self.page = page
        # TODO: Make it possible to change the `form_fields` attribute.
        self.form_fields = page.form_fields
        self.request = request
        has_steps = any(
            isinstance(struct_child.block, FormStepBlock)
            for struct_child in self.form_fields
        )
        if has_steps:
            steps = [
                Step(self, i, form_field)
                for i, form_field in enumerate(self.form_fields)
            ]
        else:
            steps = [Step(self, 0, self.form_fields)]
        super().__init__(steps)

    def clamp_index(self, index: int):
        if index < 0:
            index = 0
        if index >= len(self):
            index = len(self) - 1
        while not self[index].is_available:
            index -= 1
        return index

    @property
    def current_index(self):
        return self.request.session.get(self.page.current_step_session_key, 0)

    @property
    def current(self):
        return self[self.current_index]

    @current.setter
    def current(self, new_index: int):
        if not isinstance(new_index, int):
            raise TypeError("Use an integer to set the new current step.")
        self.request.session[self.page.current_step_session_key] = (
            self.clamp_index(new_index)
        )

    def forward(self, increment: int = 1):
        self.current = self.current_index + increment

    def backward(self, increment: int = 1):
        self.current = self.current_index - increment

    def get_session_submission(self):
        return self.page.get_session_submission(self.request)

    def get_existing_data(self):
        submission = self.get_session_submission()
        data = [] if submission is None else json.loads(submission.form_data)
        length_difference = len(self) - len(data)
        if length_difference > 0:
            data.extend([{}] * length_difference)
        return data

    def get_current_form(self):
        request = self.request
        if request.method == "POST":
            step_value = request.POST.get("step", "next")
            if step_value == "prev":
                self.backward()
            else:
                return self.current.get_form_class()(
                    request.POST,
                    request.FILES,
                    initial=self.current.get_existing_data(),
                )
        return self.current.get_form_class()(
            initial=self.current.get_existing_data()
        )

    def get_storage(self):
        return self.page.get_storage()

    def save_files(self, form):
        submission = self.get_session_submission()
        for name, field in form.fields.items():
            if isinstance(field, forms.FileField):
                file = form.cleaned_data[name]
                if file == form.initial.get(name, ""):  # Nothing submitted.
                    form.cleaned_data[name] = file.name
                    continue
                if submission is not None:
                    submission.delete_file(name)
                if not file:  # 'Clear' was checked.
                    form.cleaned_data[name] = ""
                    continue
                directory = self.request.session.session_key
                storage = self.get_storage()
                Path(storage.path(directory)).mkdir(parents=True, exist_ok=True)
                path = storage.get_available_name(
                    str(Path(directory) / file.name)
                )
                with storage.open(path, "wb+") as destination:
                    for chunk in file.chunks():
                        destination.write(chunk)
                form.cleaned_data[name] = path

    def update_data(self):
        form = self.get_current_form()
        if form.is_valid():
            form_data = self.get_existing_data()
            self.save_files(form)
            form_data[self.current_index] = form.cleaned_data
            form_data = json.dumps(form_data, cls=StreamFormJSONEncoder)
            is_complete = self.current.is_last
            submission = self.get_session_submission()
            submission.form_data = form_data
            if not submission.is_complete and is_complete:
                submission.status = submission.COMPLETE
            submission.save()
            if is_complete:
                self.current = 0
            else:
                self.forward()
            return is_complete
        return False


class AbstractSessionFormSubmission(AbstractFormSubmission):
    class Meta:
        verbose_name = _("form submission")
        verbose_name_plural = _("form submissions")
        unique_together = (("page", "session_key"), ("page", "user"))
        abstract = True

    session_key = models.CharField(
        max_length=40,
        null=True,
        default=None,
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        related_name="+",
        on_delete=models.PROTECT,
    )
    last_modification = models.DateTimeField(
        _("last modification"),
        auto_now=True,
    )
    INCOMPLETE = "incomplete"
    COMPLETE = "complete"
    REVIEWED = "reviewed"
    APPROVED = "approved"
    REJECTED = "rejected"
    STATUSES = (
        (INCOMPLETE, _("Not submitted")),
        (COMPLETE, _("Complete")),
        (REVIEWED, _("Under consideration")),
        (APPROVED, _("Approved")),
        (REJECTED, _("Rejected")),
    )
    status = models.CharField(
        max_length=10,
        choices=STATUSES,
        default=INCOMPLETE,
    )

    @staticmethod
    def get_revision_class():
        """
        You must override this in your impelementation to return something
        that inherits from ``AbstractSubmissionRevision``
        """
        return AbstractSubmissionRevision

    @property
    def is_complete(self):
        return self.status != self.INCOMPLETE

    @property
    def form_page(self):
        return self.page.specific

    def get_session(self):
        return import_module(settings.SESSION_ENGINE).SessionStore(
            session_key=self.session_key
        )

    def reset_step(self):
        session = self.get_session()
        try:
            del session[self.form_page.current_step_session_key]
        except KeyError:
            pass
        else:
            session.save()

    def get_storage(self):
        return self.form_page.get_storage()

    def get_fields(self, by_step=False):
        return self.form_page.get_form_fields(by_step=by_step)

    def get_files_by_field(self) -> typing.Dict[str, str]:
        """
        Returns a dictionary of field name : file path.
        """
        data = self.get_data(raw=True)
        files = {}
        for name, field in self.get_fields().items():
            if isinstance(field, forms.FileField):
                path = data.get(name)
                if path:
                    files[name] = path
        return files

    def get_all_files(self):
        for path in self.get_files_by_field().values():
            yield path

    def delete_file(self, field_name):
        for path in self.get_files_by_field().get(field_name, ()):
            self.get_storage().delete(path)

    def render_email(self, value):
        return value

    def render_link(self, value):
        return value

    def render_image(self, value):
        return self.get_storage().url(value)

    def render_file(self, value):
        return self.get_storage().url(value)

    def format_value(self, field, value):
        if value is None or value == "":
            return "-"
        new_value = self.form_page.format_value(field, value)
        if new_value != value:
            return new_value
        if value is True:
            return "Yes"
        if value is False:
            return "No"
        if isinstance(value, (list, tuple)):
            formatted_values = []
            for item in value:
                formatted_values.append(self.format_value(field, item))
            return ", ".join(formatted_values)
        if isinstance(value, datetime.date):
            return value
        if isinstance(field, forms.EmailField):
            return self.render_email(value)
        if isinstance(field, forms.URLField):
            return self.render_link(value)
        if isinstance(field, forms.ImageField):
            return self.render_image(value)
        if isinstance(field, forms.FileField):
            return self.render_file(value)
        if isinstance(value, SafeData) or hasattr(value, "__html__"):
            return value
        return str(value)

    def format_db_field(self, field_name, raw=False):
        method = getattr(self, "get_%s_display" % field_name, None)
        if method is not None:
            return method()
        value = getattr(self, field_name)
        if raw:
            return value
        return self.format_value(
            self._meta.get_field(field_name).formfield(), value
        )

    def get_steps_data(self, raw=False) -> typing.List[OrderedDict[str, str]]:
        """
        Returns a dictionary of {field name: rendered data value}
        """
        steps_data = json.loads(self.form_data)
        if raw:
            return steps_data
        fields_and_data_iterator = zip_longest(
            self.get_fields(by_step=True), steps_data, fillvalue={}
        )
        list_od = []
        for step_fields, step_data in fields_and_data_iterator:
            od = OrderedDict()
            for name, field in step_fields.items():
                od[name] = self.format_value(field, step_data.get(name))
            list_od.append(od)

        return list_od

    def get_data(self, raw=False, add_metadata=True):
        steps_data = self.get_steps_data(raw=raw)
        form_data = {}
        for step_data in steps_data:
            form_data.update(step_data)
        if add_metadata:
            form_data.update(
                status=self.format_db_field("status", raw=raw),
                user=self.format_db_field("user", raw=raw),
                submit_time=self.format_db_field("submit_time", raw=raw),
                last_modification=self.format_db_field(
                    "last_modification", raw=raw
                ),
            )
        return form_data

    def steps_with_data_iterator(self, raw=False):
        for step, step_data_fields, step_data in zip(
            self.form_page.get_steps(),
            self.form_page.get_data_fields(by_step=True),
            self.get_steps_data(raw=raw),
        ):
            fieldlist = []
            for field_name, field_label in step_data_fields:
                fieldlist.append(
                    (field_name, field_label, step_data[field_name])
                )
            yield (step, fieldlist)


@receiver(post_delete, sender=AbstractSessionFormSubmission)
def delete_files(sender, **kwargs):
    instance = kwargs["instance"]
    instance.reset_step()
    storage = instance.get_storage()
    for path in instance.get_all_files():
        storage.delete(path)

        # Automatically deletes ancestor folders if empty.
        directory = Path(path)
        while directory.parent != Path(directory.root):
            directory = directory.parent
            try:
                subdirectories, files = storage.listdir(directory)
            except FileNotFoundError:
                continue
            if not subdirectories and not files:
                Path(storage.path(directory)).rmdir()


class SubmissionRevisionQuerySet(models.QuerySet):
    def for_submission(self, submission):
        return self.filter(**self.model.get_filters_for(submission))

    def created(self):
        return self.filter(type=self.model.CREATED)

    def changed(self):
        return self.filter(type=self.model.CHANGED)

    def deleted(self):
        return self.filter(type=self.model.DELETED)


class AbstractSubmissionRevision(models.Model):
    class Meta:
        ordering = ("-created_at",)
        abstract = True

    objects = SubmissionRevisionQuerySet.as_manager()

    CREATED = "created"
    CHANGED = "changed"
    DELETED = "deleted"
    TYPES = (
        (CREATED, _("Created")),
        (CHANGED, _("Changed")),
        (DELETED, _("Deleted")),
    )
    type = models.CharField(
        max_length=7,
        choices=TYPES,
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
    )
    submission_ct = models.ForeignKey(
        "contenttypes.ContentType",
        on_delete=models.CASCADE,
    )
    submission_id = models.TextField()
    submission = GenericForeignKey(
        "submission_ct",
        "submission_id",
    )
    data = models.TextField()
    summary = models.TextField()

    @staticmethod
    def get_filters_for(submission):
        return {
            "submission_ct": ContentType.objects.get_for_model(
                submission._meta.model
            ),
            "submission_id": str(submission.pk),
        }

    @classmethod
    def diff_summary(cls, page, data1, data2):
        diff = []
        data_fields = page.get_data_fields()
        hidden_types = (tuple, list, dict)
        for k, label in data_fields:
            value1 = data1.get(k)
            value2 = data2.get(k)
            if value2 == value1 or not value1 and not value2:
                continue
            is_hidden = isinstance(value1, hidden_types) or isinstance(
                value2, hidden_types
            )

            # Escapes newlines as they are used as separator inside summaries.
            if isinstance(value1, str):
                value1 = value1.replace("\n", r"\n")
            if isinstance(value2, str):
                value2 = value2.replace("\n", r"\n")

            if value2 and not value1:
                diff.append(
                    (
                        (_("“%s” set.") % label)
                        if is_hidden
                        else (_("“%s” set to “%s”.")) % (label, value2)
                    )
                )
            elif value1 and not value2:
                diff.append(_("“%s” unset.") % label)
            else:
                diff.append(
                    (
                        (_("“%s” changed.") % label)
                        if is_hidden
                        else (
                            _("“%s” changed from “%s” to “%s”.")
                            % (label, value1, value2)
                        )
                    )
                )
        return "\n".join(diff)

    @classmethod
    def create_from_submission(cls, submission, revision_type):
        page = submission.form_page
        try:
            previous = cls.objects.for_submission(submission).latest(
                "created_at"
            )
        except cls.DoesNotExist:
            previous_data = {}
        else:
            previous_data = previous.get_data()
        filters = cls.get_filters_for(submission)
        data = submission.get_data(raw=True, add_metadata=False)
        data["status"] = submission.status
        if revision_type == cls.CREATED:
            summary = _("Submission created.")
        elif revision_type == cls.DELETED:
            summary = _("Submission deleted.")
        else:
            summary = cls.diff_summary(page, previous_data, data)
        if not summary:  # Nothing changed.
            return
        filters.update(
            type=revision_type,
            data=json.dumps(data, cls=StreamFormJSONEncoder),
            summary=summary,
        )
        return cls.objects.create(**filters)

    def get_data(self):
        return json.loads(self.data)


@receiver(post_save)
def create_submission_changed_revision(sender, **kwargs):
    if not issubclass(sender, AbstractSessionFormSubmission):
        return
    # ``sender`` is the concrete class of AbstractSessionFormSubmission.
    SubmissionRevision = sender.get_revision_class()
    submission = kwargs["instance"]
    created = kwargs["created"]
    SubmissionRevision.create_from_submission(
        submission,
        (SubmissionRevision.CREATED if created else SubmissionRevision.CHANGED),
    )


@receiver(post_delete)
def create_submission_deleted_revision(sender, **kwargs):
    if not issubclass(sender, AbstractSessionFormSubmission):
        return
    # ``sender`` is the concrete class of AbstractSessionFormSubmission.
    SubmissionRevision = sender.get_revision_class()
    submission = kwargs["instance"]
    SubmissionRevision.create_from_submission(
        submission, SubmissionRevision.DELETED
    )


class StreamFormMixin:
    """
    Adds StreamForm builder functionality to a Wagtail Page.

    NOTE: This is inspired by, and similar to,
    ``wagtail.contrib.forms.models.FormMixin``, however the API and behavior is
    not directly compatible with it. Ideally, this (and/or FormMixin) could be
    refactored into a single compatible API.
    """

    submissions_list_view_class = SubmissionsListView

    preview_modes = [
        ("form", _("Form")),
        ("landing", _("Landing page")),
    ]

    @property
    def current_step_session_key(self):
        return "%s:step" % self.pk

    def get_steps(self, request=None):
        if not hasattr(self, "steps"):
            steps = Steps(self, request=request)
            if request is None:
                return steps
            self.steps = steps
        return self.steps

    def get_form_fields(self, by_step=False):
        if by_step:
            return [step.get_form_fields() for step in self.get_steps()]
        form_fields = OrderedDict()
        for step_fields in self.get_form_fields(by_step=True):
            form_fields.update(step_fields)
        return form_fields

    def get_context(self, request, *args, **kwargs):
        context = super().get_context(request, *args, **kwargs)
        self.steps = self.get_steps(request)
        step_value = request.GET.get("step")
        if step_value is not None and step_value.isdigit():
            self.steps.current = int(step_value) - 1
        form = self.steps.get_current_form()
        enctype = get_form_enctype(form)
        context.update(
            steps=self.steps,
            step=self.steps.current,
            form=form,
            form_enctype=enctype,
            markups_and_bound_fields=list(
                self.steps.current.get_markups_and_bound_fields(form)
            ),
        )
        return context

    def get_storage(self):
        return default_storage

    @staticmethod
    def get_form_class_bases():
        return (forms.Form,)

    @staticmethod
    def get_submission_class():
        """
        Submission class is used to store the final form submission, after
        the user has finished their session.
        """
        return FormSubmission

    @staticmethod
    def get_session_submission_class():
        """
        Session submission class is used to stored temporary data while the
        form is being filled out, i.e. for multi-step forms.

        You must override this to return something that inherits from
        ``AbstractSessionFormSubmission``.
        """
        return AbstractSessionFormSubmission

    def get_session_submission(self, request):
        Submission = self.get_session_submission_class()
        if request.user.is_authenticated:
            user_submission = (
                Submission.objects.filter(user=request.user, page=self)
                .order_by("-pk")
                .first()
            )
            if user_submission is None:
                return Submission(user=request.user, page=self, form_data="[]")
            return user_submission

        # Ensure that anonymous users get a session key.
        if not request.session.session_key:
            request.session.create()

        user_submission = (
            Submission.objects.filter(
                session_key=request.session.session_key, page=self
            )
            .order_by("-pk")
            .first()
        )
        if user_submission is None:
            return Submission(
                session_key=request.session.session_key,
                page=self,
                form_data="[]",
            )
        return user_submission

    def create_final_submission(self, request, delete_session=True):
        """
        Converts the temporary session submission object into a final
        submission object.

        ``delete_session`` will delete all temporary ``SessionSubmission`` and
        ``SubmissionRevision`` objects from the database.
        """
        session = self.get_session_submission(request)
        submission_data = session.get_data()
        if "user" in submission_data:
            submission_data["user"] = str(submission_data["user"])
        submission = FormSubmission.objects.create(
            form_data=submission_data,
            page=session.page,
        )

        if delete_session:
            SubmissionRevision = session.get_revision_class()
            SubmissionRevision.objects.filter(submission_id=session.id).delete()
            session.delete()

        return submission

    def get_landing_page_template(self, request, *args, **kwargs):
        return self.landing_page_template

    def render_landing_page(
        self, request, form_submission=None, *args, **kwargs
    ):
        """
        Renders the landing page.

        You can override this method to return a different HttpResponse as
        landing page. E.g. you could return a redirect to a separate page.
        """
        context = self.get_context(request)
        context["form_submission"] = form_submission
        return TemplateResponse(
            request, self.get_landing_page_template(request), context
        )

    def serve(self, request, *args, **kwargs):
        """
        Handles all steps of serving a:
        * Blank/empty form.
        * Partially-filled form.
        * Completed/finalized form.

        Override this method if you'd like to customize how each step, including
        the final submission, is processed.
        """
        context = self.get_context(request)
        form = context["form"]
        if request.method == "POST" and form.is_valid():
            is_complete = self.steps.update_data()
            if is_complete:
                self.create_final_submission(request, delete_session=True)
                return self.render_landing_page(request, *args, **kwargs)
            return HttpResponseRedirect(self.url)
        return super().serve(request, *args, **kwargs)

    def serve_preview(self, request, mode_name):
        if mode_name == "landing":
            return self.render_landing_page(request)
        else:
            return super().serve_preview(request, mode_name)

    def get_submissions_list_view_class(self):
        return self.submissions_list_view_class

    def serve_submissions_list_view(self, request, *args, **kwargs):
        """
        Returns list submissions view for admin.

        `list_submissions_view_class` can be set to provide custom view class.
        Your class must be inherited from SubmissionsListView.
        """
        results_only = kwargs.pop("results_only", False)
        view = self.get_submissions_list_view_class().as_view(
            results_only=results_only
        )
        return view(request, form_page=self, *args, **kwargs)

    def get_data_fields(self, by_step=False, add_metadata=True):
        if by_step:
            stepfields = []
            for step_fields in self.get_form_fields(by_step=True):
                fieldtuples = []
                for field_name, field in step_fields.items():
                    fieldtuples.append((field_name, field.label))
                stepfields.append(fieldtuples)
            return stepfields

        data_fields = []
        if add_metadata:
            data_fields.extend(
                (
                    ("status", _("Status")),
                    ("user", _("User")),
                    ("submit_time", _("First modification")),
                    ("last_modification", _("Last modification")),
                )
            )

        # Flatten the nested set of steps -> fields into a list of fields.
        stepfields = []
        for step_data_fields in self.get_data_fields(by_step=True):
            for entry in step_data_fields:
                stepfields.append(entry)

        data_fields.extend(stepfields)
        return data_fields

    def format_value(self, field, value):
        return value


class AbstractStreamForm(StreamFormMixin, AbstractForm):
    class Meta:
        abstract = True


class AbstractEmailStreamForm(StreamFormMixin, AbstractEmailForm):
    class Meta:
        abstract = True
