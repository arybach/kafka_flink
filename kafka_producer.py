# Please implement a streaming application, for finding out popularity of PUlocationID across green and fhv trip datasets.
# Please use the datasets https://github.com/DataTalksClub/nyc-tlc-data/releases/tag/fhv/fhv_tripdata_2019-01.csv.gz
# and https://github.com/DataTalksClub/nyc-tlc-data/releases/tag/green/green_tripdata_2019-01.csv.gz

import argparse
import atexit
import csv
import json
import logging
import os
import time
import uuid
from urllib import request
import gzip
from datetime import datetime
import concurrent.futures

from confluent_kafka import Producer
from confluent_kafka.admin import AdminClient, NewTopic

logging.basicConfig(level=logging.INFO, handlers=[logging.FileHandler('producer.log')])
logger = logging.getLogger(__name__)

class ProducerCallback:
    def __init__(self, record, log_success):
        self.record = record
        self.log_success = log_success
        self.success = True
 
    def __call__(self, err, msg):
        if err:
            logger.error("Error producing record {}".format(self.record))
            self.success = False
        elif self.log_success:
            logger.info(
                "Produced {} to topic {} partition {} offset {}".format(
                    self.record, msg.topic(), msg.partition(), msg.offset()
                )
            )
            self.success = True
        else:
            self.success = True

        return self.success
        
def get_trips(file_path):
    # Open the local file
    with gzip.open(file_path, 'rt') as f:
        reader = csv.DictReader(f, delimiter=",", quotechar='"')

        for row in reader:
            yield row

def fhv_producer(args):
    logger.info("Starting fhv trip data producer")
    conf = {
        "bootstrap.servers": args.bootstrap_server,
        "linger.ms": 200,
        "partitioner": "murmur2_random",
    }
    producer = Producer(conf)
    atexit.register(lambda p: p.flush(), producer)

    for i, trip in enumerate(get_trips(args.fhv_url)):

        print(i)
        if not trip["PUlocationID"]:
            continue

        pickup_timestamp = datetime.strptime(trip["pickup_datetime"], "%Y-%m-%d %H:%M:%S")
        dropoff_timestamp = datetime.strptime(trip["dropOff_datetime"], "%Y-%m-%d %H:%M:%S")

        # dispatching_base_num, pickup_datetime, dropOff_datetime, PUlocationID, DOlocationID, SR_Flag, Affiliated_base_number
        # B00001,2019-01-01 00:30:00,2019-01-01 02:51:55,,,,B00001
        message = {
            "pickup_location_id": int(trip["PUlocationID"]),
            "dispatch_num": str(trip["dispatching_base_num"]),
            "pickup_datetime": pickup_timestamp.isoformat(),
            "dropoff_datetime": dropoff_timestamp.isoformat(),
            "affiliated_num": trip["Affiliated_base_number"],
        }

        callback = ProducerCallback(message, log_success=True)
        producer.produce(
           topic="fhv-trips",
           value=json.dumps(message),
           on_delivery=callback,
        )
        # key=str(uuid.uuid4()),
        # slow it down a bit
        time.sleep(1)

def green_producer(args):
    logger.info("Starting green trip data producer")
    conf = {
        "bootstrap.servers": args.bootstrap_server,
        "linger.ms": 200,
        "partitioner": "murmur2_random",
    }
    producer = Producer(conf)
    atexit.register(lambda p: p.flush(), producer)

    for i, trip in enumerate(get_trips(args.green_url)):

        if not trip["PULocationID"]:
            continue

        pickup_timestamp = datetime.strptime(trip["lpep_pickup_datetime"], "%Y-%m-%d %H:%M:%S")
        dropoff_timestamp = datetime.strptime(trip["lpep_dropoff_datetime"], "%Y-%m-%d %H:%M:%S")

        # VendorID, lpep_pickup_datetime, lpep_dropoff_datetime, store_and_fwd_flag, RatecodeID, PULocationID, DOLocationID, 
        # passenger_count, trip_distance, fare_amount, extra, mta_tax, tip_amount, tolls_amount, ehail_fee, improvement_surcharge,
        # total_amount, payment_type, trip_type, congestion_surcharge
        # 2,2018-12-21 15:17:29,2018-12-21 15:18:57,N,1,264,264,5,.00,3,0.5,0.5,0,0,,0.3,4.3,2,1,
        message = {
            "pickup_location_id": int(trip["PULocationID"]),
            "passenger_count": int(trip["passenger_count"]),
            "vendor_id": str(trip["VendorID"]),
            "pickup_datetime": pickup_timestamp.isoformat(),
            "dropoff_datetime": dropoff_timestamp.isoformat(),
            "trip_distance": float(trip["trip_distance"]),
            "tip_amount": float(trip["tip_amount"]),
            "fare_amount": float(trip["fare_amount"]),
        }

        callback = ProducerCallback(message, log_success=True)
        producer.produce(
           topic="green-trips",
           value=json.dumps(message),
           on_delivery=callback,
        )
        # key=str(uuid.uuid4()),
        # slow it down a bit
        time.sleep(1)
            
def main(args):

    admin_client = AdminClient({"bootstrap.servers": args.bootstrap_server})

    # Define topic names and configs
    topic_configs = {
        "fhv-trips": {"num_partitions": 1, "replication_factor": 1},
        "green-trips": {"num_partitions": 1, "replication_factor": 1}
    }

    # Check if topics already exist
    existing_topics = admin_client.list_topics()
    existing_topic_names = list(existing_topics.topics.keys())
    topic_names = topic_configs.keys()
    topics_to_create = [NewTopic(name, **config) for name, config in topic_configs.items() if name not in existing_topic_names]

    # Create new topics if they don't exist
    if topics_to_create:
        admin_client.create_topics(topics_to_create)
        print(f"Created {len(topics_to_create)} new topics: {', '.join(topic_names)}")
    else:
        print(f"Topics already exist: {', '.join(topic_names)}")

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        fhv_future = executor.submit(fhv_producer, args)
        green_future = executor.submit(green_producer, args)

    # Wait for both producers to complete
    fhv_result = fhv_future.result()
    green_result = green_future.result()
    
    # Handle any errors
    if fhv_result is not None:
        logger.error(f"fhv_producer encountered an error: {fhv_result}")
    if green_result is not None:
        logger.error(f"green_producer encountered an error: {green_result}")


if __name__ == "__main__":
    # mkdir download
    # cd download
    # wget "https://github.com/DataTalksClub/nyc-tlc-data/releases/download/fhv/fhv_tripdata_2019-01.csv.gz"
    # wget "https://github.com/DataTalksClub/nyc-tlc-data/releases/download/green/green_tripdata_2019-01.csv.gz"
    parser = argparse.ArgumentParser()
    # using broker:29092 external container port 
    parser.add_argument("--bootstrap-server", default="localhost:9092")
    parser.add_argument("--fhv-url", default="download/fhv_tripdata_2019-01.csv.gz")
    parser.add_argument("--green-url", default="download/green_tripdata_2019-01.csv.gz")
    #parser.add_argument("--fhv-url", default="https://github.com/DataTalksClub/nyc-tlc-data/releases/download/fhv/fhv_tripdata_2019-01.csv.gz")
    #parser.add_argument("--green-url", default="https://github.com/DataTalksClub/nyc-tlc-data/releases/download/green/green_tripdata_2019-01.csv.gz")
    args = parser.parse_args()
    main(args)
