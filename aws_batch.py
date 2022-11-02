import boto3
import time

class AWSBatch:
    def __init__(self, n_batches, batch_size, output_bucket, result_output_path, keywords_path, image_name,
                 aws_role, retry_attempts=3, attempt_duration=1800,
                 keep_compute_env=False, keep_job_queue=False):
        self.n_batches = n_batches
        self.batch_size = batch_size
        self.output_bucket = output_bucket
        self.result_output_path = result_output_path
        self.keywords_path = keywords_path
        self.aws_role = aws_role
        self.retry_attempts = retry_attempts
        self.batch_client = boto3.client('batch')
        self.batch_env_name = 'cc'
        self.image_name = image_name
        self.keep_compute_env = keep_compute_env
        self.keep_job_queue = keep_job_queue
        self.attempt_duration = attempt_duration

    def create_compute_environment_fargate(self):
        self.batch_client.create_compute_environment(
        computeEnvironmentName=self.batch_env_name,
        type='MANAGED',
        state='ENABLED',
        computeResources={
            'type': 'FARGATE_SPOT',
            'maxvCpus': self.n_batches,
            'subnets': [
                'subnet-3fc5e11e',
                'subnet-96402da7',
                'subnet-84326be2',
                'subnet-3470633a',
                'subnet-789d7434',
                'subnet-d4104a8b',
            ],
            'securityGroupIds': [
                'sg-c4a092d8',
            ],
        },
        tags={
            'Project': 'cc-download'
        },
        # serviceRole='arn:aws:iam::425352751544:role/aws-service-role/batch.amazonaws.com/AWSServiceRoleForBatch',
        )
        time.sleep(5)

    def create_job_queue(self):
        self.batch_client.create_job_queue(
            jobQueueName=self.batch_env_name,
            state='ENABLED',
            priority=1,
            computeEnvironmentOrder=[
                {
                    'order': 1,
                    'computeEnvironment': self.batch_env_name,
                },
            ],
        )
        time.sleep(5)

    def register_job_definition(self):
        self.batch_client.register_job_definition(
            jobDefinitionName=self.batch_env_name,
            type='container',
            containerProperties={
                'image': self.image_name,
                'resourceRequirements': [
                    {
                        'type': 'VCPU',
                        'value': '0.25',
                    },
                    {
                        'type': 'MEMORY',
                        'value': '512',
                    },
                ],
                'command': [
                    "python3",
                    "cc-download.py",
                    f"--batch_size={self.batch_size}",
                    f"--output_bucket={self.output_bucket}",
                    f"--result_output_path={self.result_output_path}",
                    f"--keywords_path={self.keywords_path}",
                ],
                'jobRoleArn': self.aws_role, #'arn:aws:iam::425352751544:role/ecsTaskExecutionRole',
                'executionRoleArn':  self.aws_role, # 'arn:aws:iam::425352751544:role/ecsTaskExecutionRole',
                'networkConfiguration': {
                        'assignPublicIp': 'ENABLED',
                }
            },
            retryStrategy={
                'attempts': self.retry_attempts,
            },
            timeout={
                'attemptDurationSeconds': self.attempt_duration
            },
            platformCapabilities=[
                'FARGATE',
            ],
        )
        time.sleep(5)

    def submit_job(self):
        self.batch_client.submit_job(
            jobName=self.batch_env_name,
            jobQueue=self.batch_env_name,
            arrayProperties={
                'size': self.n_batches,
            },
            jobDefinition=self.batch_env_name,
        )
        time.sleep(5)

    def run(self):
        if not self.keep_compute_env:
            self.create_compute_environment_fargate()
        if not self.keep_job_queue:
            self.create_job_queue()
        self.register_job_definition()
        self.submit_job()