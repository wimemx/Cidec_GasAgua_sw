# -*- coding: utf-8 -*-

# Sending html emails in Django
# Report any bugs to esat @t sleytr*net
# Evren Esat Ozkan


#download and install feedparser from http://feedparser.org
#download and install StripOGram from http://www.zope.org/Members/chrisw/StripOGram
from feedparser import _sanitizeHTML
from stripogram import html2text

from django.conf import settings
from django.template import loader, Context

from email.MIMEMultipart import MIMEMultipart
from email.MIMEText import MIMEText
from email.MIMEImage import MIMEImage
from smtplib import SMTP
import email.Charset


charset='utf-8'
smtp_server='localhost'
smtp_user=''
smtp_pass=''

email.Charset.add_charset( charset, email.Charset.SHORTEST, None, None )

def htmlmail(sbj,recip,msg,template='',texttemplate='',textmsg='',images=(), recip_name='',sender=settings.DEFAULT_FROM_EMAIL,sender_name='',charset=charset):
   """
   if you want to use Django template system:
      use `msg` and optionally `textmsg` as template context (dict)
      and define `template` and optionally `texttemplate` variables.
   otherwise msg and textmsg variables are used as html and text message sources.

   if you want to use images in html message, define physical paths and ids in tuples.
   (image paths are relative to  MEDIA_ROOT)
   example:
   images=(('email_images/logo.gif','img1'),('email_images/footer.gif','img2'))
   and use them in html like this:
   <img src="cid:img1">
   ...
   <img src="cid:img2">
   """
   html=render(msg,template)
   if texttemplate or textmsg: text=render((textmsg or msg),texttemplate)
   else: text= html2text(_sanitizeHTML(html,charset))

   msgRoot = MIMEMultipart('related')
   msgRoot['Subject'] = sbj
   msgRoot['From'] = named(sender,sender_name)
   msgRoot['To'] =  named(recip,recip_name)
   msgRoot.preamble = 'This is a multi-part message in MIME format.'

   msgAlternative = MIMEMultipart('alternative')
   msgRoot.attach(msgAlternative)
   
   msgAlternative.attach(MIMEText(text, _charset=charset))
   msgAlternative.attach(MIMEText(html, 'html', _charset=charset))

   for img in images:
      fp = open(settings.MEDIA_ROOT+img[0], 'rb')
      msgImage = MIMEImage(fp.read())
      fp.close()
      msgImage.add_header('Content-ID', '<'+img[1]+'>')
      msgRoot.attach(msgImage)

   smtp = SMTP()
   smtp.connect(smtp_server)
   if smtp_user: smtp.login(smtp_user, smtp_pass)
   smtp.sendmail(sender, recip, msgRoot.as_string())
   smtp.quit()


def render(context,template):
   if template:
      t = loader.get_template(template)
      return t.render(Context(context))
   return context

def named(mail,name):
   if name: return '%s <%s>' % (name,mail)
   return mail