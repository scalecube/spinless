FROM python:3.8

WORKDIR /opt
COPY . /opt
RUN pip install -r requirements.txt
RUN apt update && apt install -y jq
EXPOSE 5000
CMD ["python", "./start_app.py"]