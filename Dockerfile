FROM python:3.8

WORKDIR /opt
COPY . /opt
RUN pip install -r requirements.txt
RUN apt update && apt install -y jq
RUN wget -q https://storage.googleapis.com/kubernetes-helm/helm-v2.16.4-linux-amd64.tar.gz
RUN tar xzfv helm-v2.16.4-linux-amd64.tar.gz
RUN mv ./linux-amd64/helm /usr/local/bin/helm

EXPOSE 5000
CMD ["python", "./start_app.py"]