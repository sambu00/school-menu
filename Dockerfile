FROM python:3

WORKDIR /school-menu

COPY requirements.txt requirements.txt
RUN pip install -r requirements.txt

COPY . .

CMD [ "waitress-serve", "--host", "0.0.0.0", "app:app"]