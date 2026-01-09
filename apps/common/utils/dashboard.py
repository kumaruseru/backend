from django.utils.translation import gettext_lazy as _

def dashboard_callback(request, context):
    """
    Callback function for Django Unfold Dashboard.
    """
    # Dashboard rỗng, chưa có nội dung
    context.update({
        "kpi": [],
    })
    return context
