#standard library imports
from decimal import Decimal
import os
import csv

#related third party imports
import datetime
from django.contrib.auth import authenticate
from django.http import HttpResponse, HttpResponseRedirect

#local application/library specific imports
from django.shortcuts import render_to_response
from django.template.context import RequestContext
from c_center.models import ProfilePowermeter, Powermeter, ElectricData


def parse_csv(request):

    dir_path = '/Users/wime/Downloads/BaseDeDatosSATEC/'
    files = os.listdir(dir_path)
    dir_fd = os.open(dir_path, os.O_RDONLY)
    os.fchdir(dir_fd)
    html=''
    for file in files:
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

            if "MWh" in item:
                kwh = Decimal(item['MWh']) * 1000
            else:
                kwh = item['KWH']

            if "Mvarh" in item:
                kvarh = Decimal(item['Mvarh']) * 1000
            else:
                kvarh = item['KVARH']

            if "MVAh" in item:
                kvah = Decimal(item['MVAh']) * 1000
            else:
                kvah = item['KVAH']

            powerp = ProfilePowermeter.objects.get(powermeter=Powermeter.objects.get(powermeter_anotation=item['Estacion']), profile_powermeter_status=1)
            elec_data = ElectricData(
                profile_powermeter = powerp,
                medition_date = datetime.datetime.now(),
                V1 = item['V1'],
                V2 = item['V2'],
                V3 = item['V3'],
                I1 = item['I1'],
                I2 = item['I2'],
                I3 = item['I3'],
                kWL1 = item['KW1'],
                kWL2 = item['KW2'],
                kWL3 = item['KW3'],
                PFL1 = item['PF1'],
                PFL2 = item['PF2'],
                PFL3 = item['PF3'],
                kvarL1 = item['KVAR1'],
                kvarL2 = item['KVAR2'],
                kvarL3 = item['KVAR3'],
                kVAL1 = item['KVA1'],
                kVAL2 = item['KVA2'],
                kVAL3 = item['KVA3'],
                kWhIMPORT = kwh,
                kvarhNET = kvarh,
                #KVAH = kvah
            )
            if 'VL1' in item:
                elec_data.V1THD=item['VL1']
            if 'VL2' in item:
                elec_data.V2THD=item['VL2']
            if 'VL3' in item:
                elec_data.V3THD=item['VL3']
            #if 'KWH_MAX' in item:
            #    elec_data.KWH_MAX=item['KWH_MAX']
            #if 'KVARH_MAX' in item:
            #    elec_data.KVARH_MAX=item['KVARH_MAX']
            #if 'KVAH_MAX' in item:
            #    elec_data.KVARH_MAX=item['KVAH_MAX']
            elec_data.save()



            html += str(elec_data) + "<br/>"
        html += "<hr/><br/>"
    os.close(dir_fd)



    return HttpResponse(html)

def main(request):
    error = username = password = ''
    if request.user.is_authenticated():
        return HttpResponseRedirect("/main/")
    if request.method == "POST":
        username = request.POST['username']
        password = request.POST['password']
        user = authenticate(username=username, password=password)
        if user is not None:
            if user.is_active:
                return HttpResponseRedirect("/main/")
            else:
                error = "Tu cuenta ha sido desactivada, por favor ponete en contacto con tu administrador!"
        else:
            error = "Tu nombre de usuario o contrase&ntilde;a son incorrectos."
    variables = dict(username=username, password=password, error=error)
    variables_template = RequestContext(request,variables)
    return render_to_response("login.html", variables_template)


def index(request):
    variables={}
    variables_template = RequestContext(request,variables)
    return render_to_response("consumption_centers/main.html", variables_template)