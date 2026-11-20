from pathlib import Path
from urllib.parse import unquote
from urllib.parse import urlsplit

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client
from django.test import TestCase
from django.test import override_settings
from django.urls import reverse
from wagtail.contrib.forms.models import FormSubmission

from home.models import FormField
from home.models import FormPage
from home.models import MultiStepStreamFormPage
from home.models import SingleStepStreamFormPage
from home.models import WagtailPage


# A 1x1 transparent GIF used to exercise image uploads.
GIF_BYTES = (
    b"GIF89a\x01\x00\x01\x00\x80\x00\x00"
    b"\x00\x00\x00\xff\xff\xff!\xf9\x04\x01"
    b"\x00\x00\x00\x00,\x00\x00\x00\x00"
    b"\x01\x00\x01\x00\x00\x02\x02D\x01\x00;"
)


@override_settings(
    STORAGES={
        "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
        "staticfiles": {
            "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"
        },
    }
)
class FormTests(TestCase):
    def setUp(self):
        user = get_user_model().objects.create_superuser(
            username="admin",
            email="admin@example.com",
            password="password",
        )
        self.admin_client = Client()
        self.admin_client.force_login(user)
        self.home_page = WagtailPage.objects.get(slug="home")

    def publish_page(self, page):
        self.home_page.add_child(instance=page)
        page.save_revision().publish()
        return page

    def assert_submission_in_admin(
        self,
        page: FormPage | SingleStepStreamFormPage | MultiStepStreamFormPage,
        expected_data: dict[str, str],
        expected_files: dict[str, SimpleUploadedFile] | None = None,
    ):
        submission = FormSubmission.objects.get(page=page)
        file_paths = {}
        if expected_files:
            storage = page.get_storage()
            for field_name in expected_files:
                file_url_path = urlsplit(submission.form_data[field_name]).path
                relative_path = unquote(
                    file_url_path.removeprefix(storage.base_url)
                )
                file_path = Path(storage.path(relative_path))
                file_paths[field_name] = file_path
                self.addCleanup(file_path.unlink, missing_ok=True)

        self.assertEqual(
            {
                field_name: submission.form_data[field_name]
                for field_name in expected_data
            },
            expected_data,
        )
        self.assertEqual(
            {
                field_name: submission.form_data[field_name].rsplit("/", 1)[-1]
                for field_name in expected_files or {}
            },
            {
                field_name: uploaded_file.name
                for field_name, uploaded_file in (expected_files or {}).items()
            },
        )
        if expected_files:
            storage = page.get_storage()
            for field_name, uploaded_file in expected_files.items():
                file_url_path = urlsplit(submission.form_data[field_name]).path
                self.assertTrue(file_url_path.startswith(storage.base_url))
                file_path = file_paths[field_name]
                self.assertTrue(
                    file_path.is_file(), f"{uploaded_file.name} was not saved"
                )
                uploaded_file.seek(0)
                self.assertEqual(file_path.read_bytes(), uploaded_file.read())

        if not isinstance(page, FormPage):
            return

        response = self.admin_client.get(
            reverse("wagtailforms:list_submissions", args=(page.pk,))
        )
        self.assertEqual(response.status_code, 200)
        for value in expected_data.values():
            self.assertContains(response, value)

    def test_formpage(self):
        # Create page.
        page = self.publish_page(FormPage(title="Contact", slug="contact"))
        page.form_fields.add(FormField(label="Name", field_type="singleline"))
        page.save_revision().publish()

        # Render public page.
        response = self.client.get(page.url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'name="name"')

        # Submit public form submission.
        response = self.client.post(page.url, {"name": "Ada Lovelace"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Thank you.")

        # Check for submission in admin.
        self.assert_submission_in_admin(page, {"name": "Ada Lovelace"})

    def test_singlestepstreamformpage(self):
        # Create page.
        page = self.publish_page(
            SingleStepStreamFormPage(
                title="Single-step form",
                slug="single-step-form",
                form_fields=[
                    (
                        "sf_singleline",
                        {
                            "field_label": "Name",
                            "help_text": "",
                            "required": True,
                        },
                    ),
                    (
                        "sf_multiline",
                        {
                            "field_label": "Biography",
                            "help_text": "",
                            "required": False,
                        },
                    ),
                    (
                        "sf_number",
                        {
                            "field_label": "Age",
                            "help_text": "",
                            "required": False,
                        },
                    ),
                    (
                        "sf_checkbox",
                        {
                            "field_label": "Subscribe",
                            "help_text": "",
                            "default_value": False,
                        },
                    ),
                    (
                        "sf_radios",
                        {
                            "field_label": "Favorite color",
                            "help_text": "",
                            "required": False,
                            "choices": ["Red", "Blue"],
                        },
                    ),
                    (
                        "sf_dropdown",
                        {
                            "field_label": "Country",
                            "help_text": "",
                            "required": False,
                            "choices": ["Canada", "United States"],
                        },
                    ),
                    (
                        "sf_checkboxes",
                        {
                            "field_label": "Interests",
                            "help_text": "",
                            "required": False,
                            "checkboxes": ["Reading", "Writing"],
                        },
                    ),
                    (
                        "sf_date",
                        {
                            "field_label": "Birth date",
                            "help_text": "",
                            "required": False,
                        },
                    ),
                    (
                        "sf_time",
                        {
                            "field_label": "Best time",
                            "help_text": "",
                            "required": False,
                        },
                    ),
                    (
                        "sf_datetime",
                        {
                            "field_label": "Appointment",
                            "help_text": "",
                            "required": False,
                        },
                    ),
                    (
                        "sf_image",
                        {
                            "field_label": "Profile image",
                            "help_text": "",
                            "required": False,
                        },
                    ),
                    (
                        "sf_file",
                        {
                            "field_label": "Attachment",
                            "help_text": "",
                            "required": False,
                        },
                    ),
                ],
            )
        )

        # Render public page.
        response = self.client.get(page.url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'name="name"')
        self.assertContains(response, 'name="biography"')
        self.assertContains(response, 'name="age"')
        self.assertContains(response, 'name="subscribe"')
        self.assertContains(response, 'name="favorite-color"')
        self.assertContains(response, 'name="country"')
        self.assertContains(response, 'name="interests"')
        self.assertContains(response, 'name="birth-date"')
        self.assertContains(response, 'name="best-time"')
        self.assertContains(response, 'name="appointment_0"')
        self.assertContains(response, 'name="appointment_1"')
        self.assertContains(response, 'name="profile-image"')
        self.assertContains(response, 'name="attachment"')

        profile_image = SimpleUploadedFile(
            "profile.gif",
            GIF_BYTES,
            content_type="image/gif",
        )
        attachment = SimpleUploadedFile(
            "notes.txt",
            b"Submission attachment",
            content_type="text/plain",
        )

        # Submit public form submission.
        response = self.client.post(
            page.url,
            {
                "name": "Grace Hopper",
                "biography": "Mathematician and Rear Admiral",
                "age": "85",
                "subscribe": "on",
                "favorite-color": "Blue",
                "country": "United States",
                "interests": ["Reading", "Writing"],
                "birth-date": "1906-12-09",
                "best-time": "09:30",
                "appointment_0": "2026-11-20",
                "appointment_1": "16:05",
                "profile-image": profile_image,
                "attachment": attachment,
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Thank you.")

        # Check for submission in admin.
        self.assert_submission_in_admin(
            page,
            {
                "name": "Grace Hopper",
                "biography": "Mathematician and Rear Admiral",
                "age": "85",
                "subscribe": "Yes",
                "favorite-color": "Blue",
                "country": "United States",
                "interests": "Reading, Writing",
                "birth-date": "1906-12-09",
                "best-time": "09:30:00",
                "appointment": "2026-11-20T16:05:00Z",
            },
            {
                "profile-image": profile_image,
                "attachment": attachment,
            },
        )

    def test_multistepstreamformpage(self):
        # Create page.
        page = self.publish_page(
            MultiStepStreamFormPage(
                title="Multi-step form",
                slug="multi-step-form",
                form_fields=[
                    (
                        "sf_step",
                        {
                            "name": "First step",
                            "form_fields": [
                                (
                                    "sf_singleline",
                                    {
                                        "field_label": "First name",
                                        "help_text": "",
                                        "required": True,
                                    },
                                ),
                                (
                                    "sf_multiline",
                                    {
                                        "field_label": "Biography",
                                        "help_text": "",
                                        "required": False,
                                    },
                                ),
                                (
                                    "sf_number",
                                    {
                                        "field_label": "Age",
                                        "help_text": "",
                                        "required": False,
                                    },
                                ),
                                (
                                    "sf_checkbox",
                                    {
                                        "field_label": "Subscribe",
                                        "help_text": "",
                                        "default_value": False,
                                    },
                                ),
                                (
                                    "sf_radios",
                                    {
                                        "field_label": "Favorite color",
                                        "help_text": "",
                                        "required": False,
                                        "choices": ["Red", "Blue"],
                                    },
                                ),
                                (
                                    "sf_dropdown",
                                    {
                                        "field_label": "Country",
                                        "help_text": "",
                                        "required": False,
                                        "choices": ["Canada", "United States"],
                                    },
                                ),
                                (
                                    "sf_checkboxes",
                                    {
                                        "field_label": "Interests",
                                        "help_text": "",
                                        "required": False,
                                        "checkboxes": ["Reading", "Writing"],
                                    },
                                ),
                                (
                                    "sf_date",
                                    {
                                        "field_label": "Birth date",
                                        "help_text": "",
                                        "required": False,
                                    },
                                ),
                                (
                                    "sf_time",
                                    {
                                        "field_label": "Best time",
                                        "help_text": "",
                                        "required": False,
                                    },
                                ),
                                (
                                    "sf_datetime",
                                    {
                                        "field_label": "Appointment",
                                        "help_text": "",
                                        "required": False,
                                    },
                                ),
                                (
                                    "sf_image",
                                    {
                                        "field_label": "Profile image",
                                        "help_text": "",
                                        "required": False,
                                    },
                                ),
                                (
                                    "sf_file",
                                    {
                                        "field_label": "Attachment",
                                        "help_text": "",
                                        "required": False,
                                    },
                                ),
                            ],
                        },
                    ),
                    (
                        "sf_step",
                        {
                            "name": "Second step",
                            "form_fields": [
                                (
                                    "sf_singleline",
                                    {
                                        "field_label": "Last name",
                                        "help_text": "",
                                        "required": True,
                                    },
                                )
                            ],
                        },
                    ),
                ],
            )
        )

        # Render public page.
        response = self.client.get(page.url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'name="first-name"')
        self.assertContains(response, 'name="biography"')
        self.assertContains(response, 'name="age"')
        self.assertContains(response, 'name="subscribe"')
        self.assertContains(response, 'name="favorite-color"')
        self.assertContains(response, 'name="country"')
        self.assertContains(response, 'name="interests"')
        self.assertContains(response, 'name="birth-date"')
        self.assertContains(response, 'name="best-time"')
        self.assertContains(response, 'name="appointment_0"')
        self.assertContains(response, 'name="appointment_1"')
        self.assertContains(response, 'name="profile-image"')
        self.assertContains(response, 'name="attachment"')

        profile_image = SimpleUploadedFile(
            "profile.gif",
            GIF_BYTES,
            content_type="image/gif",
        )
        attachment = SimpleUploadedFile(
            "notes.txt",
            b"Submission attachment",
            content_type="text/plain",
        )

        # Submit public multi-step form submission.
        response = self.client.post(
            page.url,
            {
                "first-name": "Katherine",
                "biography": "Mathematician",
                "age": "101",
                "subscribe": "on",
                "favorite-color": "Red",
                "country": "United States",
                "interests": ["Reading", "Writing"],
                "birth-date": "1918-08-26",
                "best-time": "10:30",
                "appointment_0": "2026-11-20",
                "appointment_1": "16:05",
                "profile-image": profile_image,
                "attachment": attachment,
            },
        )
        self.assertEqual(response.status_code, 302)
        response = self.client.get(page.url)
        self.assertEqual(response.status_code, 200)

        # Submit second step of multi-step form.
        self.assertContains(response, 'name="last-name"')
        response = self.client.post(page.url, {"last-name": "Johnson"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Thank you.")

        # Check for submission in admin.
        self.assert_submission_in_admin(
            page,
            {
                "first-name": "Katherine",
                "biography": "Mathematician",
                "age": "101",
                "subscribe": "Yes",
                "favorite-color": "Red",
                "country": "United States",
                "interests": "Reading, Writing",
                "birth-date": "1918-08-26",
                "best-time": "10:30:00",
                "appointment": "2026-11-20T16:05:00Z",
                "last-name": "Johnson",
            },
            {
                "profile-image": profile_image,
                "attachment": attachment,
            },
        )
