FROM python:3.10.7

COPY cc-downloader .

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

# download and install argos models
#COPY download_install_argos_models.py .
#RUN python3 download_install_argos_models.py


## the command is submitted directly to AWS batch as a job definition:
# python cc-download.py --batch_size=100 --output_bucket=cc-extract --result_output_path=cc-download-test --keywords='https://github.com/jakob-ra/cc-download/raw/main/keywords.csv'


## to push the dockerfile to Amazon Elastic Container Registry:
# start docker daemon
# docker build -t cc-download .
# docker tag cc-download:latest public.ecr.aws/r9v1u7o6/cc-download:latest
# docker tag cc-download:latest public.ecr.aws/r9v1u7o6/cc-download-translate:latest
# aws ecr-public get-login-password --region us-east-1 | docker login --username AWS --password-stdin public.ecr.aws
# docker push public.ecr.aws/r9v1u7o6/cc-download:latest
# docker push public.ecr.aws/r9v1u7o6/cc-download-translate:latest

