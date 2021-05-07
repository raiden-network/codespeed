FROM python:3.9-slim

RUN mkdir /codespeed
WORKDIR /codespeed

RUN apt-get -y update && apt-get install -y nginx

COPY requirements.txt /codespeed
COPY raiden/deploy/nginx.default-site.conf /etc/nginx/sites-enabled/default

RUN pip install --no-cache-dir -r requirements.txt
RUN pip install --no-cache-dir gunicorn

ENV DJANGO_SETTINGS_MODULE raiden.settings
EXPOSE 80

CMD /etc/init.d/nginx start && gunicorn raiden.wsgi
