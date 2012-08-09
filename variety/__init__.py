from decimal import Decimal
import decimal
import random
import string
from urlparse import urlparse
from django.core.validators import email_re

#-----libs for write_pdf
#import cgi
#import StringIO
#from django.template.loader import get_template
#from xhtml2pdf import pisa

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

def unique_from_array(array):
    #returns an array with unique values
    #ej. [1,1,2,3,3,,1] regresa [1,2,3]
    u = []
    for x in array:
        if x not in u:
            if x !='':
                u.append(x)

    return u

def get_post_data(request):
    """
    cleans the POST data, turns the strings into str(),
    and the numbers into long or float
    """
    datos_post={}
    for postdata in request.POST:
        #print str(postdata)
        dato=request.POST[str(postdata)].strip()

        try:
            dato=Decimal(dato)
        except InvalidOperation:
            datos_post[str(postdata)]=request.POST[str(postdata)]
        else:
            if(dato%1 == 0): #si es un numero entero
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