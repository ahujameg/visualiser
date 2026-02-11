FROM python:3.10 as base

WORKDIR /apps

FROM base AS runtime

ENV DJANGO_SETTINGS_MODULE=visualiser.settings

COPY requirements.txt .

RUN apt-get update && apt-get install -y r-base

RUN pip install -r requirements.txt

COPY . /apps/

CMD ["gunicorn", "--bind", ":7000", "--workers", "1", "--timeout", "36000", "--graceful-timeout", "36000", "config.wsgi:application"]
