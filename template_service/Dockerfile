FROM python:3.12.9-slim-bullseye

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

RUN pip install --upgrade pip

COPY ./requirements.txt .
COPY ../contracts /contracts
RUN pip install -r requirements.txt && pip install -e /contracts

COPY ./app .
