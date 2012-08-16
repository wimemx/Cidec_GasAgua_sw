#standard library imports
import os
import csv

#related third party imports
import datetime
from django.contrib.auth import authenticate, login, logout
from django.http import HttpResponse, HttpResponseRedirect

#local application/library specific imports
from django.shortcuts import render_to_response
from django.template.context import RequestContext
from c_center.models import ProfilePowermeter, ElectricData
from c_center.views import main_page

def parse_csv(request):

    dir_path = '/Users/wime/Downloads/BaseDeDatosSATEC/'
    files = os.listdir(dir_path)
    dir_fd = os.open(dir_path, os.O_RDONLY)
    os.fchdir(dir_fd)
    html=''
    for file in files:
        if file == '.DS_Store':
            continue
        data = csv.reader(open(file))
        # Read the column names from the first line of the file
        fields = data.next()
        for row in data:
        # Zip together the field names and values
            items = zip(fields, row)
            item = {}
            # Add the value to our dictionary
            for (name, value) in items:
                item[name] = value.strip()


            powerp = ProfilePowermeter.objects.order_by('?')

            elec_data = ElectricData(
                profile_powermeter = powerp[0],
                powermeter_serial = item['powermeter_serial'],
                medition_date = datetime.datetime.now(),
                V1 = item['V1'],
                V2 = item['V2'],
                V3 = item['V3'],
                I1 = item['I1'],
                I2 = item['I2'],
                I3 = item['I3'],
                kWL1 = item['kWL1'],
                kWL2 = item['kWL2'],
                kWL3 = item['kWL3'],
                kvarL1 = item['kvarL1'],
                kvarL2 = item['kvarL2'],
                kvarL3 = item['kvarL3'],
                kVAL1 = item['kVAL1'],
                kVAL2 = item['kVAL2'],
                kVAL3 = item['kVAL3'],
                PFL1 = item['PFL1'],
                PFL2 = item['PFL2'],
                PFL3 = item['PFL3'],
                kW = item['kW'],
                kvar = item['kvar'],
                kVA = item['kVA'],
                PF = item['PF'],
                In = item['In'],
                FREQ = item['FREQ'],
                kWIMPSDMAX = item['kWIMPSDMAX'],
                kWIMPACCDMD = item['kWIMPACCDMD'],
                kVASDMAX = item['kVASDMAX'],
                kVAACCDMD = item['kVAACCDMD'],
                I1DMDMAX = item['I1DMDMAX'],
                I2DMDMAX = item['I2DMDMAX'],
                I3DMDMAX = item['I3DMDMAX'],
                kWhIMPORT = item['kWhIMPORT'],
                kWhEXPORT = item['kWhEXPORT'],
                kvarhNET = item['kvarhNET'],
                kvarhIMPORT = item['kvarhIMPORT'],
                V1THD = item['V1THD'],
                V2THD = item['V2THD'],
                V3THD = item['V3THD'],
                I1THD = item['I1THD'],
                I2THD = item['I2THD'],
                I3THD = item['I3THD']
            )

            elec_data.save()



            html += str(elec_data) + "<br/>"
        html += "<hr/><br/>"
    os.close(dir_fd)



    return HttpResponse(html)

def _login(request):
    error = username = password = ''
    if request.user.is_authenticated():
        return HttpResponseRedirect("/main/")
    if request.method == "POST":
        username = request.POST['username']
        password = request.POST['password']
        user = authenticate(username=username, password=password)
        if user is not None:
            if user.is_active:
                login(request, user)
                return HttpResponseRedirect("/main/")
            else:
                error = "Tu cuenta ha sido desactivada, por favor ponete en contacto con tu administrador!"
        else:
            error = "Tu nombre de usuario o contrase&ntilde;a son incorrectos."
    variables = dict(username=username, password=password, error=error)
    variables_template = RequestContext(request,variables)
    return render_to_response("login.html", variables_template)


def index(request):
    if not request.user.is_authenticated():
        return HttpResponseRedirect("/")
    return main_page(request)

def logout_page(request):
    logout(request)
    return HttpResponseRedirect('/')