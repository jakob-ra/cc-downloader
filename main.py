from athena_lookup import Athena_lookup
import pandas as pd
import os
import s3fs
from aws_config import aws_configure_credentials
from aws_batch import AWSBatch
import yaml

if __name__ == '__main__':
    ## read config file
    with open("config.yml", "r", encoding='utf8') as ymlfile:
        cfg = yaml.safe_load(ymlfile)

    ## authenticate to AWS
    aws_configure_credentials(cfg['credentials_csv_filepath'], cfg['region'], cfg['profile_name'])

    # available_crawls = pd.read_csv('common-crawls.txt')

    ## run athena lookup
    result_output_path = cfg['result_output_path'] + '/' + '_'.join(cfg['crawls']) # path in output_bucket to store the downloads in batches
    aws_params = {
        'region': cfg['region'],
        'catalog': 'AwsDataCatalog',
        'database': 'ccindex',
        'bucket': cfg['output_bucket'],
        'path': cfg['index_output_path'],
    }
    url_keywords = pd.read_csv(cfg['url_keywords_path'], header=None, usecols=[0]).squeeze().tolist()

    athena_lookup = Athena_lookup(aws_params, cfg['s3path_url_list'], cfg['crawls'],
                                  cfg['n_subpages_per_domain'], url_keywords, limit_cc_table=None,
                                  keep_ccindex=True, limit_pages_url_keywords=cfg['limit_pages_url_keywords'])
    athena_lookup.run_lookup()

    ## run batch job
    req_batches = int(athena_lookup.download_table_length//cfg["batch_size"] + 1)
    print(f'Splitting {athena_lookup.download_table_length} subpages into {req_batches} batches of size {cfg["batch_size"]}.')
    print(f'Estimated costs: {0.33*athena_lookup.download_table_length*10-6}$.')

    aws_batch = AWSBatch(req_batches, cfg["batch_size"], cfg['output_bucket'], result_output_path,
                         cfg['keywords_path'], cfg['image_name'], cfg['batch_role'], retry_attempts=cfg['retry_attempts'],
                         attempt_duration=cfg['attempt_duration'], keep_compute_env=True, keep_job_queue=True)
    aws_batch.run()
