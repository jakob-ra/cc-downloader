import pandas as pd
import boto3
from warcio.archiveiterator import ArchiveIterator
import time
from io import BytesIO
from bs4 import BeautifulSoup, SoupStrainer
import os
import argparse
import awswrangler as wr
import numpy as np
from utils import exponential_backoff
from passage_extraction import PassageExtractor

def fetch_process_warc_records(row, s3client, keywords):
    """Fetch all WARC records defined by filenames and offsets in batch,
    parse the records and the contained HTML, return all paragraphs containing at least one of the
    keywords.csv"""

    only_paragraphs = SoupStrainer('p')

    warc_path, offset, end = row.warc_filename, str(row.warc_record_offset), str(row.warc_record_end)

    rangereq = 'bytes={}-{}'.format(offset, end)

    response = exponential_backoff(s3client.get_object, Bucket='commoncrawl', Key=warc_path, Range=rangereq)

    record_stream = BytesIO(response["Body"].read())

    extracts = []
    for record in ArchiveIterator(record_stream):
        page = record.content_stream().read()

        soup = BeautifulSoup(page, 'lxml', parse_only=only_paragraphs)

        text = soup.get_text()

        extractor = PassageExtractor(text, keywords)
        extracts += extractor.extract_relevant_passages()

    return extracts


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch_size", type=int, required=True)
    parser.add_argument("--output_bucket", type=str, required=True)
    parser.add_argument("--result_output_path", type=str, required=True)
    parser.add_argument("--keywords_path", type=str, required=True) # default='https://github.com/jakob-ra/cc-download/raw/main/cc-download/keywords.csv')
    args = parser.parse_args()

    keywords = pd.read_csv(args.keywords_path).squeeze().tolist()

    if "AWS_BATCH_JOB_ARRAY_INDEX" in os.environ:
        batch_n = os.environ['AWS_BATCH_JOB_ARRAY_INDEX']
        batch_n = int(batch_n)
        print(f'Processing batch {batch_n}.')
    else:
        batch_n = 0
        print('Processing first batch (no array index found).')

    session = boto3.Session(region_name='us-east-1')

    sts = session.client("sts")
    print(sts.get_caller_identity())

    # read cc-index table with warc filenames and byte positions
    query = f'SELECT * FROM urls_merged_cc_to_download OFFSET {batch_n} LIMIT {args.batch_size} '
    df = wr.athena.read_sql_query(sql=query, database="ccindex", boto3_session=session)
    assert len(df) > 1, "Empty input table!"

    # initialize s3
    s3client = boto3.client('s3', region_name='us-east-1', use_ssl=False)

   # download paragraphs and fill into new column
    print('Starting download...')
    start = time.process_time()
    df['paragraphs'] = df.apply(lambda row: fetch_process_warc_records(row, s3client, keywords), axis=1)
    print(f'Success! Finished downloading in {time.process_time() - start} seconds.')
    print(f'Share of domains mentioning at least one keyword: {df.groupby("url_host_registered_domain").paragraphs.apply(lambda x: len(x[x.str.len()>0])).mean()}')
    print(f'Share of subpages mentioning at least one keyword: {len(df.paragraphs[df.paragraphs.str.len()>0])/len(df)}')

    # drop offsets
    df.drop(columns=['warc_filename', 'warc_record_offset', 'warc_record_end'], inplace=True)

    # drop pages without any paragraphs
    df = df[df.paragraphs.str.len() > 0].copy(deep=True)

    # save to S3
    s3_path = f's3://{args.output_bucket}/{args.result_output_path}/batch_n_{batch_n}.csv'
    df.to_csv(s3_path, index=False)
    print(f'Results saved to: {s3_path}')