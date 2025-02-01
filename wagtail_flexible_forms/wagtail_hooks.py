from django.contrib.contenttypes.models import ContentType
from wagtail import hooks
from wagtail.models import get_page_models
from wagtail.permissions import page_permission_policy

from wagtail_flexible_forms.models import StreamFormMixin


@hooks.register("filter_form_submissions_for_user")
def stream_forms(user, editable_forms):
    """
    Append Page instances derived from ``StreamFormMixin`` to the queryset
    of editiable_forms.
    """
    # Get content types of pages that inherit from StreamFormMixin.
    sf_models = [
        model
        for model in get_page_models()
        if issubclass(model, (StreamFormMixin,))
    ]
    sf_types = list(ContentType.objects.get_for_models(*sf_models).values())

    # Get all pages this user can access.
    all_editable_pages = (
        page_permission_policy.instances_user_has_permission_for(user, "change")
    )

    # Filter down StreamFormMixin pages this user can access.
    sf_editable_forms = all_editable_pages.filter(content_type__in=sf_types)

    # Combine the previous hook's ``editable_forms`` with our ``editable_forms``.
    combined_forms_pks = list(
        sf_editable_forms.values_list("pk", flat=True)
    ) + list(editable_forms.values_list("pk", flat=True))
    combined_editable_forms = all_editable_pages.filter(
        pk__in=combined_forms_pks
    )
    return combined_editable_forms
