from rbac.models import *
VIEW = Operation.objects.get(operation_name="view")
CREATE = Operation.objects.get(operation_name="create")
DELETE = Operation.objects.get(operation_name="delete")
UPDATE = Operation.objects.get(operation_name="update")
# Create your views here.
def add_data_context_permissions(request):
    """Permission Asigments
    show a form for data context permission asigment
    """
    if has_permission(request.user, CREATE, "data_context_permissions"):
        #has perm to view graphs, now check what can the user see
        datacontext = DataContextPermission.objects.filter(user_role__user=request.user)

        set_default_session_vars(request, datacontext)
        #valid years for reporting
        request.session['years'] = [__date.year
                                    for __date in
                                    ElectricData.objects.all().dates('medition_date', 'year')]

        template_vars = {"type":"graphs", "datacontext":datacontext,
                         'empresa': request.session['main_building'],
                         'consumer_unit': request.session['consumer_unit']
        }
        template_vars_template = RequestContext(request, template_vars)
        return render_to_response("consumption_centers/main.html", template_vars_template)
    else:
        return render_to_response("generic_error.html", RequestContext(request))