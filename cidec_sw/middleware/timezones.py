from django.utils import timezone


class TimezoneMiddleware(object):
    def process_request(self, request):
        tz = request.session.get('timezone')
        if tz:
            timezone.activate(tz)


class YearsMiddleware(object):
    def process_request(self, request):
        if 'years' not in request.session:
            request.session["years"] = ["2012", "2013"]
