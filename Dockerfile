FROM python:3.8

WORKDIR /opt
COPY . /opt
RUN pip install -r requirements.txt
RUN curl -LO https://storage.googleapis.com/spinnaker-artifacts/spin/$(curl -s https://storage.googleapis.com/spinnaker-artifacts/spin/latest)/linux/amd64/spin
RUN chmod +x spin
RUN mv spin /usr/local/bin/spin
RUN mkdir /root/.spin
RUN apt update && apt install -y jq
EXPOSE 5000
CMD ["python", "./start_app.py"]