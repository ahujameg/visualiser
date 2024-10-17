FROM python:3.10 as base

WORKDIR /apps

FROM base AS runtime

ENV DJANGO_SETTINGS_MODULE=visualiser.settings

COPY requirements.txt .

RUN pip install -r requirements.txt

COPY . /apps/

CMD ["gunicorn", "--bind", ":7000", "--workers", "3", "config.wsgi:application"]