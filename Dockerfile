FROM python:3.10.6 AS python-build

ENV PYTHONUNBUFFERED 1

COPY requirements.txt /tmp/
WORKDIR /tmp
RUN echo "Installing requirements.txt"
RUN pip install -r requirements.txt

WORKDIR /code

CMD ["python", "./bot_signals.py"]
