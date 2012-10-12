#standard library imports
import os
import csv
from itertools import cycle
from random import uniform, randrange
from datetime import timedelta
from decimal import Decimal
import pytz #for timezone support

#related third party imports
import datetime
from django.contrib.auth import authenticate, login, logout
from django.http import HttpResponse, HttpResponseRedirect

#local application/library specific imports
from django.shortcuts import render_to_response
from django.template.context import RequestContext
from c_center.models import ProfilePowermeter, ElectricData, ElectricDataTemp
from c_center.views import main_page

from django.shortcuts import redirect, render

def set_timezone(request):
    if request.method == 'POST':
        request.session['django_timezone'] = pytz.timezone(request.POST['timezone'])
        return redirect('/')
    else:
        return render(request, 'set_timezone.html', {'timezones': pytz.common_timezones})

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
    return HttpResponseRedirect('/main/?logout')

def changedate(key):
    """
    sets all the data in intervals of 3 hours
    """
    data = ElectricData.objects.filter(profile_powermeter__pk=key).order_by("-medition_date")
    initial_date = ElectricData.objects.filter(profile_powermeter__pk=3).order_by("-medition_date")[:1]
    initial_date = initial_date[0].medition_date
    print "initial_date", initial_date
    for dato in data:
        print "antes", dato.medition_date
        initial_date -= timedelta(minutes=5)
        dato.medition_date = initial_date
        dato.save()
        print "despues", dato.medition_date

def dummy_data_generator_2000():
    """
    Generates dummy electric meditions
    """
    for item in ['1', '2', '3']:
        i=0
        initial_date = datetime.datetime(2012,01,01,00,00)
        profile = ProfilePowermeter.objects.get(pk=int(item))
        kwh=Decimal(900090)
        kvarh_net=Decimal(388.6)
        for item in cycle(['1.8','2']):
            i += 1
            initial_date += timedelta(minutes=5)
            kwh += Decimal(randrange(0, 100010))
            kvarh_net += Decimal(uniform(0, 12.1))
            elec_data = ElectricData(
                profile_powermeter = profile,
                powermeter_serial = "9304404",
                medition_date = initial_date,
                V1 = round(Decimal(uniform(127.5, 128.9)),6),
                V2 = round(Decimal(uniform(127.5, 128.9)),6),
                V3 = round(Decimal(uniform(127.5, 128.9)),6),
                I1 = round(Decimal(uniform(1.168, 1.219)),6),
                I2 = round(Decimal(uniform(1.168, 1.219)),6),
                I3 = round(Decimal(uniform(1.168, 1.219)),6),
                kWL1 = round(Decimal(uniform(83.8, 87.5)),6),
                kWL2 = round(Decimal(uniform(83.8, 87.5)),6),
                kWL3 = round(Decimal(uniform(83.8, 87.5)),6),
                kvarL1 = round(Decimal(uniform(-129.6, -125.3)),6),
                kvarL2 = round(Decimal(uniform(-129.6, -125.3)),6),
                kvarL3 = round(Decimal(uniform(-129.6, -125.3)),6),
                kVAL1 = round(Decimal(uniform(150.6, 155.03)),6),
                kVAL2 = round(Decimal(uniform(150.6, 155.03)),6),
                kVAL3 = round(Decimal(uniform(150.6, 155.03)),6),
                PFL1 = round(Decimal(uniform(-.5549, 1)),6),
                PFL2 = round(Decimal(uniform(-.5549, 1)),6),
                PFL3 = round(Decimal(uniform(-.5549, 1)),6),
                kW = round(Decimal(uniform(251.5, 258.7)),6),
                kvar = round(Decimal(uniform(-388.8, -376.7)),6),
                kVA = round(Decimal(uniform(453.08, 466.3)),6),
                PF = round(Decimal(uniform(-.5549, 1)),6),
                In = round(Decimal(uniform(3.51, 3.65)),6),
                FREQ = round(Decimal(uniform(59.97, 59.99)),6),
                kWIMPSDMAX = round(Decimal(0.043204),6),
                kWIMPACCDMD = round(Decimal(uniform(1.16, 2.1)),6),
                kVASDMAX = round(Decimal(.129613),6),
                kVAACCDMD = round(Decimal(uniform(2.11, 3.7)),6),
                I1DMDMAX = round(Decimal(.000200),6),
                I2DMDMAX = round(Decimal(.000200),6),
                I3DMDMAX = round(Decimal(.000200),6),
                kWhIMPORT = round(kwh,6),
                kWhEXPORT = Decimal(0),
                kvarhNET = round(kvarh_net,6),
                kvarhIMPORT = round(kvarh_net,6),
                V1THD = Decimal(item),
                V2THD = Decimal(item),
                V3THD = Decimal(item),
                I1THD = Decimal(142.3),
                I2THD = Decimal(142.3),
                I3THD = Decimal(142.3)
            )
            elec_data.save()
            print i, " - ", elec_data
            if i >= 65512:
                break

def data_exchange():
    electric_d=ElectricData.objects.all()
    for el in electric_d:
        elec=ElectricDataTemp(
            profile_powermeter = el.profile_powermeter,
            powermeter_serial = el.powermeter_serial,
            medition_date = el.medition_date,
            V1 = el.V1,
            V2 = el.V2,
            V3 = el.V3,
            I1 = el.I1,
            I2 = el.I2,
            I3 = el.I3,
            kWL1 = el.kWL1,
            kWL2 = el.kWL2,
            kWL3 = el.kWL3,
            kvarL1 = el.kvarL1,
            kvarL2 = el.kvarL2,
            kvarL3 = el.kvarL3,
            kVAL1 = el.kVAL1,
            kVAL2 = el.kVAL2,
            kVAL3 = el.kVAL3,
            PFL1 = el.PFL1,
            PFL2 = el.PFL2,
            PFL3 = el.PFL3,
            kW = el.kW,
            kvar = el.kvar,
            TotalkVA = el.kVA,
            PF = el.PF,
            FREQ = el.FREQ,
            TotalkWhIMPORT =  el.kWhIMPORT,
            kvahTOTAL = el.kvahTOTAL,
            TotalkvarhIMPORT = el.kvarhIMPORT,
            kWhL1 = el.kWhL1,
            kWhL2 = el.kWhL2,
            kwhL3 = el.kwhL3,
            kvarhL1 = el.kvarhL1,
            kvarhL2 = el.kvarhL2,
            kvarhL3 = el.kvarhL3,
            kVAhL1 = el.kVAhL1,
            kVAhL2 = el.kVAhL2,
            kVAhL3 = el.kVAhL3,
            kW_import_sliding_window_demand = el.kW_import_sliding_window_demand,
            kvar_import_sliding_window_demand = el.kvar_import_sliding_window_demand,
            kVA_sliding_window_demand = el.kVA_sliding_window_demand
        )
        elec.save()
    print "success :D"