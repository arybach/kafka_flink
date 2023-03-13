import os, sys
from pyflink.datastream import StreamExecutionEnvironment
from confluent_kafka.admin import AdminClient, NewTopic
from pyflink.table import EnvironmentSettings, StreamTableEnvironment, CsvTableSink, WriteMode, DataTypes
#from pyflink.table.types import Kafka

# Kafka broker address (broker:29092) external container port is at: ip addr show docker0
bootstrap_servers = 'localhost:9092'

# Create KafkaAdminClient instance
admin_client = AdminClient({"bootstrap.servers": bootstrap_servers})


def main():

    # Create streaming environment
    env = StreamExecutionEnvironment.get_execution_environment()

    settings = EnvironmentSettings.new_instance() \
        .in_streaming_mode() \
        .build()

    # create table environment
    tbl_env = StreamTableEnvironment.create(stream_execution_environment=env,
                                            environment_settings=settings)

    # create kafka configuration
    kafka_config = {
        'bootstrap.servers': 'localhost:9092',
        'group.id': 'tripsdata'
    }

    # define the default catalog and database to use
    tbl_env.get_config().get_configuration().set_string("catalog.default_catalog.type", "memory")
    tbl_env.get_config().get_configuration().set_string("catalog.default_catalog.default_database", "tripsdb")

    # add kafka connector dependency
    kafka_jar = os.path.join(os.path.abspath(os.path.dirname(__file__)),
                             'flink-sql-connector-kafka-1.16.1.jar')

    tbl_env.get_config().get_configuration().set_string("pipeline.jars", "file://{}".format(kafka_jar))

    # create dtatabase and use it
    tbl_env.execute_sql("""
        CREATE DATABASE IF NOT EXISTS tripsdb COMMENT 'Database for trips data'
    """)

    tbl_env.execute_sql("""
        USE tripsdb
    """)

    # create Kafka Source Table with DDL for fhv data
    fhv_src_ddl = f"""
        CREATE TABLE fhv_trips (
            pickup_location_id INT,
            pickup_datetime TIMESTAMP(3),
            proctime AS PROCTIME()
        ) WITH (
            'connector' = 'kafka',
            'topic' = 'fhv-trips',
            'properties.bootstrap.servers' = '{kafka_config["bootstrap.servers"]}',
            'properties.group.id' = '{kafka_config["group.id"]}',
            'format' = 'json',
            'json.fail-on-missing-field' = 'false',
            'json.ignore-parse-errors' = 'true'
        )
    """

    tbl_env.execute_sql(fhv_src_ddl)
    # create and initiate loading of source Table
    tbl_fhv = tbl_env.from_path('fhv_trips')
    tbl_fhv.print_schema()

    #######################################################################
    # Create Kafka Source Table with DDL for green data
    #######################################################################
    green_src_ddl = f"""
        CREATE TABLE green_trips (
            pickup_location_id INT,
            pickup_datetime TIMESTAMP(3),
            proctime AS PROCTIME()
        ) WITH (
            'connector' = 'kafka',
            'topic' = 'green-trips',
            'properties.bootstrap.servers' = '{kafka_config["bootstrap.servers"]}',
            'properties.group.id' = '{kafka_config["group.id"]}',
            'format' = 'json',
            'json.fail-on-missing-field' = 'false',
            'json.ignore-parse-errors' = 'true'
        )
    """

    tbl_env.execute_sql(green_src_ddl)
    # create and initiate loading of source Table
    tbl_green = tbl_env.from_path('green_trips')
    tbl_green.print_schema()
    ###############################################################
    # Create new Kafka topic
    ###############################################################

    # Define topic configuration
    topic_name = 'popular-pickup-location'
    num_partitions = 1
    replication_factor = 1
    topic_config = {"max.message.bytes": 15048576}

    # Create topic
    topic = NewTopic(topic=topic_name, num_partitions=num_partitions, replication_factor=replication_factor, config=topic_config)
    admin_client.create_topics([topic])

    #####################################################################
    # Union fhv and green tables and calculate popular pickup_location_id
    #####################################################################
    popular_location_sql = """
        SELECT
            TUMBLE_START(proctime, INTERVAL '3' MINUTE) AS window_start,
            TUMBLE_END(proctime, INTERVAL '3' MINUTE) AS window_end,
            CAST(pickup_location_id as INT) AS pickup_location_id,
            CAST(COUNT(*) AS BIGINT) AS pickup_count
        FROM (
            SELECT pickup_location_id, proctime
            FROM fhv_trips
            UNION ALL
            SELECT pickup_location_id, proctime
            FROM green_trips
        )
        GROUP BY TUMBLE(proctime, INTERVAL '3' MINUTE), pickup_location_id
    """

    # Write popular pickup_location aggregations to sink table
    popular_tbl = tbl_env.sql_query(popular_location_sql)
    popular_tbl.print_schema()

    ###############################################################
    # Create Kafka Sink Table
    ###############################################################
    sink_ddl = f"""
        CREATE TABLE popular_pickup_location (
            window_start TIMESTAMP(3),
            window_end TIMESTAMP(3),
            pickup_location_id INT,
            pickup_count BIGINT
        ) WITH (
            'connector' = 'kafka',
            'topic' = 'popular-pickup-location',
            'properties.bootstrap.servers' = '{kafka_config["bootstrap.servers"]}',
            'properties.group.id' = '{kafka_config["group.id"]}',
            'format' = 'json',
            'json.fail-on-missing-field' = 'false',
            'json.ignore-parse-errors' = 'true'
        )
    """
    tbl_env.execute_sql(sink_ddl)

    # write time windowed aggregations to sink table
    # result = popular_tbl.execute_insert('popular_pickup_location').wait()
    popular_tbl.execute_insert('popular_pickup_location')

    # Create additonal topic to aggregate popular-pickup-location data
    #topic_name = 'popular-pickup-location'
    topic_name = 'top-pickup-location'
    num_partitions = 1
    replication_factor = 1
    topic_config = {"max.message.bytes": 15048576}

    # Create topic
    topic = NewTopic(topic=topic_name, num_partitions=num_partitions, replication_factor=replication_factor, config=topic_config)
    admin_client.create_topics([topic])

    top_location_sql = """
        SELECT
            pickup_location_id,
            SUM(pickup_count) AS total_pickup_count,
            TUMBLE_START(proctime(), INTERVAL '20' MINUTE) AS window_start,
            TUMBLE_END(proctime(), INTERVAL '20' MINUTE) AS window_end
        FROM popular_pickup_location
        GROUP BY
            pickup_location_id,
            TUMBLE(proctime(), INTERVAL '20' MINUTE)
    """

    top_tbl = tbl_env.sql_query(top_location_sql)
    top_tbl.print_schema()

    ###############################################################
    # Define the retract stream sink
    ###############################################################
    top_ddl = f"""
        CREATE TABLE top_pickup_location (
            pickup_location_id INT,
            pickup_count BIGINT,
            window_start TIMESTAMP(3),
            window_end TIMESTAMP(3)
        ) WITH (
            'connector' = 'kafka',
            'topic' = 'top-pickup-location',
            'properties.bootstrap.servers' = '{kafka_config["bootstrap.servers"]}',
            'properties.group.id' = '{kafka_config["group.id"]}',
            'properties.auto.offset.reset' = 'earliest',
            'format' = 'json',
            'json.fail-on-missing-field' = 'false',
            'json.ignore-parse-errors' = 'true'
        );
    """
    tbl_env.execute_sql(top_ddl)

    # write time windowed aggregations to sink table
    # result = popular_tbl.execute_insert('popular_pickup_location').wait()
    top_tbl.execute_insert('top_pickup_location')

    # Select location_id from popular_pickup_location and print to console
    location_id_sql = """
        SELECT pickup_location_id, sum(pickup_count)
        FROM top_pickup_location
        GROUP BY pickup_location_id
    """

    location_id_tbl = tbl_env.sql_query(location_id_sql)
    location_id_tbl.to_pandas().to_csv(sys.stdout, index=False, header=False)

if __name__ == '__main__':
    main()
