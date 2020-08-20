FROM python:3.8

WORKDIR /opt
# Install Helm
RUN curl -fsSL -o get_helm.sh https://raw.githubusercontent.com/helm/helm/master/scripts/get-helm-3
RUN chmod 700 get_helm.sh
RUN ./get_helm.sh

#Install Terraform
RUN wget https://releases.hashicorp.com/terraform/0.12.24/terraform_0.12.24_linux_amd64.zip
RUN unzip -u terraform_0.12.24_linux_amd64.zip
RUN mv terraform /usr/local/bin/terraform

# Install kubectl
RUN curl -LO https://storage.googleapis.com/kubernetes-release/release/`curl -s https://storage.googleapis.com/kubernetes-release/release/stable.txt`/bin/linux/amd64/kubectl
RUN chmod +x kubectl
RUN mv kubectl /usr/local/bin/kubectl

# Install aws libraries
RUN curl -o aws-iam-authenticator https://amazon-eks.s3.us-west-2.amazonaws.com/1.15.10/2020-02-22/bin/linux/amd64/aws-iam-authenticator
RUN chmod +x aws-iam-authenticator
RUN  mv aws-iam-authenticator /usr/local/bin/aws-iam-authenticator

ENV APP_WORKING_DIR /opt/app
ENV GIT_SSH_COMMAND="ssh -o IdentitiesOnly=yes -i /root/.ssh/id_rsa -F /dev/null -oStrictHostKeyChecking=no"

COPY . /opt
RUN pip install -r requirements.txt
RUN apt update && apt install -y jq vim mc tree less

EXPOSE 5000
CMD ["/bin/sh", "-c", "./start_app.sh"]