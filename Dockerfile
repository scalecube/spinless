FROM python:3.8

WORKDIR /opt
COPY . /opt
RUN pip install -r requirements.txt
RUN apt update && apt install -y jq vim mc
RUN wget -q https://storage.googleapis.com/kubernetes-helm/helm-v2.14.1-linux-amd64.tar.gz
RUN tar xzfv helm-v2.14.1-linux-amd64.tar.gz
RUN mv ./linux-amd64/helm /usr/local/bin/helm
RUN wget https://releases.hashicorp.com/terraform/0.12.24/terraform_0.12.24_linux_amd64.zip
RUN unzip -u terraform_0.12.24_linux_amd64.zip
RUN mv terraform /usr/local/bin/terraform
RUN curl -LO https://storage.googleapis.com/kubernetes-release/release/`curl -s https://storage.googleapis.com/kubernetes-release/release/stable.txt`/bin/linux/amd64/kubectl
RUN chmod +x kubectl
RUN mv kubectl /usr/local/bin/kubectl

ENV TF_WORKING_DIR /opt/infrastructure


EXPOSE 5000
CMD ["/bin/sh", "-c", "./start_app.sh"]