FROM python:3.12

ADD .flaskenv .
ADD pdfmrg.py .
ADD requirements.txt .
ADD app app

RUN pip install -r requirements.txt

CMD [ "flask", "run", "--host=0.0.0.0" ]