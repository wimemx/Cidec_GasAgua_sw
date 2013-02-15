from datetime import datetime, timedelta
import pytz
from functools import wraps
from time import time
from decimal import Decimal
import decimal
from decimal import InvalidOperation
import random
import string
import re
from urlparse import urlparse
from django.core.validators import email_re
from django.utils import timezone


#-----libs for write_pdf
#import cgi
#import StringIO
#from django.template.loader import get_template
#from xhtml2pdf import pisa

def get_hour_from_datetime(datetime_input):
    hour_datetime = datetime(year=datetime_input.year,
                             month=datetime_input.month,
                             day=datetime_input.day,
                             hour=datetime_input.hour,
                             tzinfo=datetime_input.tzinfo)

    return hour_datetime

def get_week_start_datetime_end_datetime_tuple (
        year,
        month,
        week
):
    first_day_of_month = datetime(year=year, month=month, day=1)
    first_day_of_first_week = first_day_of_month - timedelta(days=first_day_of_month.weekday())
    week_delta = timedelta(weeks=1)
    week_number = 1
    first_day_of_week = first_day_of_first_week
    while (first_day_of_week + week_delta).year <= year and\
          (first_day_of_week + week_delta).month <= month and\
          week_number < week:

        week_number += 1
        first_day_of_week += week_delta

    week_start = first_day_of_week.replace(hour=0,
                                           minute=0,
                                           second=0)

    week_end = week_start + week_delta
    return week_start, week_end


def get_weeks_number_in_month (
        year,
        month
):
    # TODO - Implement this function
    pass


def get_week_of_month_from_datetime(datetime_variable):
    """Get the week number of the month for a datetime
    datetime_variable = the date
    returns the week number (int)
    """
    first_day_of_month = datetime(year=datetime_variable.year,
        month=datetime_variable.month, day=1)
    first_day_first_week = first_day_of_month - timedelta(days=first_day_of_month.weekday())
    week_delta = timedelta(weeks = 1)
    datetime_next = first_day_first_week + week_delta
    week_number = 1
    while datetime_next <= datetime_variable:
        week_number += 1
        datetime_next += week_delta

    return week_number


def random_string_generator(size=6, chars=string.ascii_uppercase + string.digits):
    """Random String Generator

    Keyword arguments:
    size -- longitud de la cadena (default 6)
    chars -- caracteres de entre los que generara la cadena (default [A-Z0-9])
    >>> id_generator()
    'G5G74W'
    >>> id_generator(3, "6793YUIO")
    'Y3U'

    """
    return ''.join(random.choice(chars) for x in range(size))


#def write_pdf(template_src, context_dict):
#    """
#    genera un pdf, recibe la ruta del template y el context para el template
#    """
#    template = get_template(template_src)
#    context = contexto(context_dict)
#    html  = template.render(context)
#    result = StringIO.StringIO()
#    pdf = pisa.pisaDocument(StringIO.StringIO(
#        html.encode("ISO-8859-1")), result)
#    if not pdf.err:
#        return HttpResponse(result.getvalue(), mimetype='application/pdf')
#    return HttpResponse("Los Gremlin's se comieron tu PDF! %s" % cgi.escape(html))

def validate_url(url):
    """ Checks if a url is valid """
    o = urlparse(url)
    if o.netloc!='':
        return True
    else:
        return False


def validate_string(string):
    arePat = re.compile(r'[^\w\s\-\'"]' , re.UNICODE)
    string_arr = string.split(" ")
    for i in string_arr:
        if i == "" or arePat.search(i):
            return False
    return True

def unique_from_array(array):
    #returns an array with unique values
    #ej. [1,1,2,3,3,,1] regresa [1,2,3]
    u = []
    for x in array:
        if x not in u:
            if x !='':
                u.append(x)

    return u

def get_post_data(post):
    """
    cleans the POST data, turns the strings into str(),
    and the numbers into long or float
    """
    datos_post={}
    for postdata in post:
        #print str(postdata)
        dato=post[str(postdata)].strip()

        try:
            dato=Decimal(dato)
        except InvalidOperation:
            datos_post[str(postdata)]=post[str(postdata)]
        else:
            if dato%1 == 0: #si es un numero entero
                datos_post[str(postdata)]=long(dato)
            else: #si tiene decimales
                datos_post[str(postdata)]=float(dato)
    return datos_post

def moneyfmt(value, places=2, curr='', sep=',', dp='.',
             pos='', neg='-', trailneg=''):
    """Convert Decimal to a money( or number ) formatted string.

    places:  required number of places after the decimal point
    curr:    optional currency symbol before the sign (may be blank)
    sep:     optional grouping separator (comma, period, space, or blank)
    dp:      decimal point indicator (comma or period)
             only specify as blank when places is zero
    pos:     optional sign for positive numbers: '+', space or blank
    neg:     optional sign for negative numbers: '-', '(', space or blank
    trailneg:optional trailing minus indicator:  '-', ')', space or blank

    >>> d = Decimal('-1234567.8901')
    >>> moneyfmt(d, curr='$')
    '-$1,234,567.89'
    >>> moneyfmt(d, places=0, sep='.', dp='', neg='', trailneg='-')
    '1.234.568-'
    >>> moneyfmt(d, curr='$', neg='(', trailneg=')')
    '($1,234,567.89)'
    >>> moneyfmt(Decimal(123456789), sep=' ')
    '123 456 789.00'
    >>> moneyfmt(Decimal('-0.02'), neg='<', trailneg='>')
    '<0.02>'

    """
    q = Decimal(10) ** -places      # 2 places --> '0.01'
    sign, digits, exp = value.quantize(q).as_tuple()
    result = []
    digits = map(str, digits)
    build, next = result.append, digits.pop
    if sign:
        build(trailneg)
    for i in range(places):
        build(next() if digits else '0')
    build(dp)
    if not digits:
        build('0')
    i = 0
    while digits:
        build(next())
        i += 1
        if i == 3 and digits:
            i = 0
            build(sep)
    build(curr)
    build(neg if sign else pos)
    return ''.join(reversed(result))

def is_number(number):
    """ check if a string is number

    returns false if not numeric, else returns digit(long or float)

    """
    try:
        dato=Decimal(number)
    except decimal.InvalidOperation:
        return False
    else:
        if dato%1 == 0: #si es un numero entero
            dato=long(dato)
        else: #si tiene decimales
            dato=float(dato)
        return dato

def is_valid_email(email):
    return True if email_re.match(email) else False

def scale_dimensions(width, height, longest_side):
    """ Calculates image ratio given a longest side
    returns a tupple with ajusted width, height
    """
    if width > height:
        if width > longest_side:
            ratio = longest_side*1./width
            return int(width*ratio), int(height*ratio)
    elif height > longest_side:
        ratio = longest_side*1./height
        return int(width*ratio), int(height*ratio)
    return width, height

def convert_to_utc(time, tz):
    """this returns the offset in int form as well"""
    now_dt = datetime.utcnow()
    #get a date object
    date_dt = now_dt.date()
    #combine the current date object with our given time object
    dt = datetime.combine(date_dt, time)
    #get an timezone object for the source timezone
    src_tz = pytz.timezone(str(tz))
    #stamp the source datetime object with the src timezone
    src_dt = src_tz.localize(dt)
    #get the offset from utc to given timezone
    offset = str(int(src_dt.strftime("%z"))).rstrip('0')
    #convert the source datetime object to
    utc_dt = src_dt.astimezone(pytz.utc)
    #return the converted time and the offset in integer format
    return utc_dt.time(), int(offset)

def convert_from_utc(time, tz):
    now_dt = datetime.now()
    date = now_dt.date()
    dt = datetime.combine(date, time)
    dest = pytz.timezone(str(tz))
    dt = dt.replace(tzinfo=pytz.utc)
    dest_dt = dt.astimezone(dest)
    return dest_dt.time()

def timed(f):
    @wraps(f)
    def wrapper(*args, **kwds):
        start = time()
        result = f(*args, **kwds)
        elapsed = time() - start
        print "%s took %d seconds to finish" % (f.__name__, elapsed)
        return result
    return wrapper