#coding:utf-8

# Python imports
import datetime

# Django imports
import django.http
import django.shortcuts
import django.template.context
import django.utils.timezone

# Cidec imports
import c_center.models

# Other imports
import pylab


def render_prototype(
        request
):

    template_variables = dict()

    # Get the consumer unit
    try:
        consumer_unit = c_center.models.ConsumerUnit.objects.get(pk=7)

    except c_center.models.ConsumerUnit.DoesNotExist:
        raise django.http.Http404

    timezone_current = django.utils.timezone.get_current_timezone()
    datetime_start = datetime.datetime(
                         year=2012,
                         month=12,
                         day=1,
                         tzinfo=timezone_current)

    datetime_end = datetime.datetime(
                       year=2012,
                       month=12,
                       day=10,
                       tzinfo=timezone_current)

    datetime_unix_zero = datetime.datetime(
                             year=1970,
                             month=1,
                             day=1,
                             tzinfo=timezone_current)

    unix_zero_time_delta = datetime_start - datetime_unix_zero
    unix_zero_time_delta_seconds =\
        unix_zero_time_delta.seconds +\
        (unix_zero_time_delta.days * 24 * 3600)

    electric_data_raw =\
        c_center.models.ElectricDataTemp.objects.filter(
            profile_powermeter=consumer_unit.profile_powermeter,
            medition_date__gte=datetime_start,
            medition_date__lte=datetime_end,
        ).values('medition_date', 'kW')

    dependent_data_list = []
    independent_data_list = []
    counter = 0
    for values_dictionary in electric_data_raw:
        dependent_data_list.append(float(str(values_dictionary['kW'])))
        medition_date_current = values_dictionary['medition_date']

        if counter < 10:
            print medition_date_current

        counter += 1

        medition_date_current_time_delta =\
            medition_date_current - datetime_start

        medition_date_current_time_delta_seconds =\
            medition_date_current_time_delta.seconds +\
            (medition_date_current_time_delta.days * 24 * 3600)

        independent_data_list.append(medition_date_current_time_delta_seconds)

    data_rows = []
    for (independent_data_item, dependent_data_item) in\
        zip(independent_data_list, dependent_data_list):

        data_row_dictionary =\
            dict(datetime=independent_data_item + unix_zero_time_delta_seconds,
                 electric_data=dependent_data_item)

        data_rows.append(data_row_dictionary)

    template_variables['data_rows'] = data_rows

    #
    # Curve fit regression
    #
    list_items_number = len(independent_data_list)
    curve_fits_number = list_items_number / 12

    dependent_data_list_curve_fit = []
    independent_data_list_curve_fit = []
    for curve_fit_index in range(0, curve_fits_number):
        curve_fit_fixed_index_start = curve_fit_index * 12
        curve_fit_fixed_index_end = curve_fit_fixed_index_start + 12
        curve_fit_coefficients_current =\
            pylab.polyfit(
                independent_data_list[curve_fit_fixed_index_start:curve_fit_fixed_index_end],
                dependent_data_list[curve_fit_fixed_index_start:curve_fit_fixed_index_end],
                2)

        a_coefficient = curve_fit_coefficients_current[0]
        b_coefficient = curve_fit_coefficients_current[1]
        c_coefficient = curve_fit_coefficients_current[2]
        #d_coefficient = curve_fit_coefficients_current[3]

        curve_fit_function_current =\
            lambda x, a=a_coefficient, b=b_coefficient, c=c_coefficient: (a*x**2)+(b*x)+c

        hour_delta_seconds = 3600
        minute_delta_seconds = 300
        for minute_index in range(0, 12):
            delta_seconds_current =\
                (curve_fit_index * hour_delta_seconds) +\
                (minute_index * minute_delta_seconds)

            independent_data_list_curve_fit.append(delta_seconds_current)
            dependent_data_list_curve_fit.append(
                curve_fit_function_current(delta_seconds_current))

    data_rows_curve_fit = []
    for (independent_data_item_curve_fit, dependent_data_item_curve_fit) in\
    zip(independent_data_list_curve_fit, dependent_data_list_curve_fit):

        data_rows_curve_fit_dictionary =\
        dict(datetime=independent_data_item_curve_fit + unix_zero_time_delta_seconds,
            electric_data=dependent_data_item_curve_fit)

        data_rows_curve_fit.append(data_rows_curve_fit_dictionary)

    template_variables['data_rows_curve_fit'] = data_rows_curve_fit

    curve_fit_coefficients = pylab.polyfit(
                                 independent_data_list,
                                 dependent_data_list,
                                 2)

    curve_fit_a = curve_fit_coefficients[0]
    curve_fit_b = curve_fit_coefficients[1]
    curve_fit_c = curve_fit_coefficients[2]

    curve_fit_function =\
        lambda x, a=curve_fit_a, b=curve_fit_b, c=curve_fit_c: (a*x**2)+(b*x)+c

    time_delta_max = datetime_end - datetime_start
    time_delta_max_seconds =\
        time_delta_max.seconds + (time_delta_max.days * 24 * 3600)

    five_minute_delta = datetime.timedelta(minutes=5)
    five_minute_delta_seconds =\
        five_minute_delta.seconds + (five_minute_delta.days * 24 * 3600)

    independent_data_list_regression =\
        pylab.arange(0, time_delta_max_seconds, five_minute_delta_seconds)

    data_rows_regression = []
    for independent_data_item_regression in independent_data_list_regression:
        dependent_data_item_regression = curve_fit_function(
                                             independent_data_item_regression)

        data_row_regression_dictionary =\
            dict(datetime=independent_data_item_regression +\
                          unix_zero_time_delta_seconds,
                 electric_data=dependent_data_item_regression)

        data_rows_regression.append(data_row_regression_dictionary)

    template_variables['data_rows_regression'] = data_rows_regression

    template_context = django.template.context.RequestContext(
                           request,
                           template_variables)

    return django.shortcuts.render_to_response("prototype.html",
                                               template_context)