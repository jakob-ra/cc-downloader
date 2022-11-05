from athena_lookup import Athena_lookup
import pandas as pd
import os
import s3fs
from aws_config import aws_config_credentials
from aws_batch import AWSBatch
import yaml

## read config file
with open("config.yml", "r", encoding='utf8') as ymlfile:
    cfg = yaml.safe_load(ymlfile)

## authenticate to AWS
aws_config_credentials(cfg['credentials_csv_filepath'], cfg['region'], cfg['profile_name'])

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

aws_batch = AWSBatch(req_batches, cfg["batch_size"], cfg['output_bucket'], result_output_path,
                     cfg['keywords_path'], cfg['image_name'], cfg['batch_role'], retry_attempts=cfg['retry_attempts'],
                     attempt_duration=cfg['attempt_duration'], keep_compute_env=True, keep_job_queue=True)
aws_batch.run()

df = pd.read_csv('s3://cc-extract/cc-download-test/batch_n_0.csv')



# estimate aws batch cost
compute_time = req_batches * 600 / 3600
0.01293507*compute_time*0.25 + 0.00142037*compute_time*0.5 # FARGATE SPOT
0.0004*req_batches*batch_size/1000 # S3 requests
0.37*len(crawls) # athena lookup cost
# athena retrieval costs

# instance_price_per_hour = 0.0035
# time_for_completion = 0.1 # 6 minutes
# instance_price_per_hour*req_batches*time_for_completion*len(available_crawls)


res = pd.read_csv(athena_lookup.download_table_location)

df = pd.read_csv(athena_lookup.download_table_location, skiprows=range(1, 17000 * batch_size), nrows=batch_size, header=0)






## read results
df = pd.concat([pd.read_csv(f's3://{output_bucket}/{result_output_path}/batch_n_{i}.csv') for i in range(req_batches)])

df = pd.concat([pd.read_csv(f's3://{output_bucket}/cc-download/CC-MAIN-2020-24/batch_n_{i}.csv') for i in range(40)])

# df = pd.read_csv(f's3://{output_bucket}/cc-download/CC-MAIN-2020-16/batch_n_{0}.csv')

from ast import literal_eval
df['paragraphs'] = df.paragraphs.apply(literal_eval)
df = df.explode('paragraphs')
df['paragraphs'] = df.paragraphs.str.strip()
df.drop(columns=['warc_filename', 'warc_record_offset', 'warc_record_end'], inplace=True)



## detect language
from langdetect import detect
def detect_lang(text: str) -> str:
    try:
        return detect(text)
    except:
        return None

df['lang'] = df.paragraphs.str[:50].apply(detect_lang)



## Descriptives language distribution
lang_counts = df.lang.value_counts().to_frame(name='count')
lang_counts['share'] = lang_counts/lang_counts.sum()
lang_counts['cum_share'] = lang_counts.share.cumsum()

lang_codes = pd.read_csv('/Users/Jakob/Downloads/language-codes.csv', names=['lang', 'language'])
lang_codes = lang_codes.append({'lang': 'zh-cn', 'language': 'Chinese'}, ignore_index=True)
lang_counts = lang_counts.reset_index(names='lang').merge(lang_codes, on='lang', how='left')
lang_counts = lang_counts.merge(argos_models, left_on='lang', right_on='from_code', how='left')
lang_counts = lang_counts.iloc[1:] # remove english

import matplotlib.pyplot as plt
import numpy as np
fig, ax = plt.subplots(figsize=(14,6))
lang_counts.share.plot(ax=ax, kind='bar', color='grey')
ax.set_xticklabels(lang_counts.language, rotation=45, ha='right')
for i in range(len(lang_counts)):
    if np.isnan(lang_counts.package_version.iloc[i]):
        ax.get_xticklabels()[i].set_color("red")
plt.grid()
plt.tight_layout()
plt.show()

lang_counts
ax.get_xticklabels()

lang_counts.head(12) # take top 12 languages, 95% of content


import argostranslate.translate

def load_argos_model(from_code, to_code):
    installed_languages = argostranslate.translate.get_installed_languages()
    from_lang = list(filter(lambda x: x.code == from_code, installed_languages))[0]
    to_lang = list(filter(lambda x: x.code == to_code, installed_languages))[0]
    model = from_lang.get_translation(to_lang)

    return model

def argos_translate(model, text):
    try:
        return model.translate(text)
    except:
        return None

model = load_argos_model(from_code, to_code)
df['translated'] = None
df[df.lang == 'de'].paragraphs.iloc[:100].apply(lambda x: argos_translate(model, x))

model.translate()









# get rid of old compute environment
# try:
#     # batch_client.deregister_job_definition(jobDefinition=batch_env_name)
#     batch_client.update_job_queue(jobQueue=batch_env_name, state='DISABLED')
#     time.sleep(2)
#     batch_client.delete_job_queue(jobQueue=batch_env_name)
#     time.sleep(2)
#     batch_client.update_compute_environment(
#         computeEnvironment=batch_env_name,
#         state='DISABLED',
#     )
#     time.sleep(2)
#     batch_client.delete_compute_environment(
#         computeEnvironment='cc-download'
#     )
#     time.sleep(2)
# except Exception as e:
#     print(e)