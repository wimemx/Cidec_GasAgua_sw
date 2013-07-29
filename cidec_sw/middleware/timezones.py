from django.utils import timezone

class TimezoneMiddleware(object):
    def process_request(self, request):
        """tz = request.session.get('timezone')
        if tz:
            timezone.activate(tz)"""

