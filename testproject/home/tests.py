from django.contrib.auth import get_user_model
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

    def assert_submission_in_admin(self, page, expected_data):
        submission = FormSubmission.objects.get(page=page)
        self.assertEqual(
            {
                field_name: submission.form_data[field_name]
                for field_name in expected_data
            },
            expected_data,
        )

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
                        {"field_label": "Name", "required": True},
                    )
                ],
            )
        )

        # Render public page.
        response = self.client.get(page.url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'name="name"')

        # Submit public form submission.
        response = self.client.post(page.url, {"name": "Grace Hopper"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Thank you.")

        # Check for submission in admin.
        self.assert_submission_in_admin(page, {"name": "Grace Hopper"})

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
                                        "required": True,
                                    },
                                )
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

        # Submit public multi-step form submission.
        response = self.client.post(page.url, {"first-name": "Katherine"})
        self.assertEqual(response.status_code, 302)
        response = self.client.get(page.url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'name="last-name"')
        response = self.client.post(page.url, {"last-name": "Johnson"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Thank you.")

        # Check for submission in admin.
        self.assert_submission_in_admin(
            page,
            {"first-name": "Katherine", "last-name": "Johnson"},
        )
