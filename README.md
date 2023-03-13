% pull repo
git clone https://github.com/arybach/kafka_flink.git

% set env
sudo apt install software-common-properties
sudo add-apt-repository ppa:deadsnakes/ppa
sudo apt install python3.9 pyhton3.9-venv
sudo update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.10 1
sudo update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.9 2
sudo update-alternatives --set python3 /usr/bin/python3.9

python3 -V

python3.9 -m venv .venv
source .venv/bin/activate

% modify options
docker-compose.yml - specify test topics if any
in kafka_producer.py - generates messages

% install jdk11
sudo apt-get install openjdk-11-jdk
export JAVA_HOME=/usr/lib/jvm/java-1.11.0-openjdk-amd64
update ~/.bashrc file if needed

% add sql connector 
wget  https://repo.maven.apache.org/maven2/org/apache/flink/flink-sql-connector-kafka/1.16.1/flink-sql-connector-kafka-1.16.1.jar
flink-sql-connector-kafka-1.16.1.jar % to match  flink python flink-python-1.16.1.jar

% modify path to sql connector in python code
pip install apache-flink[connector-kafka]

% modify flink-conf.yaml if needed

% to import pyflink package in vs code
pip install -r requirements.txt
% or one by one
pip install apache-flink
pip install pykafka
pip install counfluent_kafka

% start all the containers
docker-compose up -d 

% confluent control center
http://localhost:9021/
can check cluster and messages after generation process begins

% download dataset - can be read from the url in the process, but from local is more reliable 
wget "https://github.com/DataTalksClub/nyc-tlc-data/releases/download/fhv/fhv_tripdata_2019-01.csv.gz"
wget "https://github.com/DataTalksClub/nyc-tlc-data/releases/download/green/green_tripdata_2019-01.csv.gz"

% two terminal bash windows
% should be with venv already activated
% to start message generation (modify time.sleep() or it will take a while)
bash1 > python3 kafka_producer.py

% this will create sink topics and kick off sql jobs
bash2 > python3 flink_calcs.py 

% flink_calcs.py runs for a while, so to check if sql is working it is easier to paste snippets from flink.sql into sql-client
docker exec -it sql-client /opt/sql-client/sql-client.sh

% forward ports 8081 (flink), 9021 (confluent manager)
% more detailed info below
% SQL CLI for Apache Flink® on Docker®

sudo chown -R 1001:root /path/to/zookeeper/data && sudo chmod -R g+rwX,o+rX,o-w /path/to/zookeeper/data

This docker-compose provides an Apache Flink® SQL CLI image updated to the 1.16.0 version. It's inspired by [this](https://github.com/wuchong/flink-sql-demo/tree/v1.11-EN/sql-client).

It makes use of the `flink:1.16.0-scala_2.12` images and of the `ftisiot/flink-sql-client:1.16.0` which is based on the same `flink:1.16.0-scala_2.12` image.

The `sql-client` service maps a `~/kafkacerts/` folder to `/certs` which can be used to create and pass files like Keystores when SSL authentication is needed (e.g. with Apache Kafka®).

Includes the SQL connectors to:
* [Elasticsearch® 7](https://repo.maven.apache.org/maven2/org/apache/flink/flink-sql-connector-elasticsearch7/1.16.0/flink-sql-connector-elasticsearch7-1.16.0.jar)
* [Apache Kafka®](https://repo.maven.apache.org/maven2/org/apache/flink/flink-sql-connector-kafka/1.16.0/flink-sql-connector-kafka-1.16.0.jar)
* [AVRO](https://repo.maven.apache.org/maven2/org/apache/flink/flink-sql-avro-confluent-registry/1.16.0/flink-sql-avro-confluent-registry-1.16.0.jar)
* [JDBC](https://repo.maven.apache.org/maven2/org/apache/flink/flink-connector-jdbc/1.16.0/flink-connector-jdbc-1.16.0.jar)
* [PostgreSQL 42.5.0](https://jdbc.postgresql.org/download/postgresql-42.5.0.jar)
* [Flink Faker](https://github.com/knaufk/flink-faker/releases/download/v0.5.0/flink-faker-0.5.1.jar) allowing to [generate fake data](https://github.com/knaufk/flink-faker)

Apache Flink Web UI is now available at `localhost:8081`

To Access the SQL CLI, execute
```
docker exec -it sql-client /opt/sql-client/sql-client.sh
```

This will popup Flink sql cli

```
Reading default environment from: file:/opt/flink/conf/sql-client-conf.yaml
No session environment specified.

Command history file path: /root/.flink-sql-history
                                   ▒▓██▓██▒
                               ▓████▒▒█▓▒▓███▓▒
                            ▓███▓░░        ▒▒▒▓██▒  ▒
                          ░██▒   ▒▒▓▓█▓▓▒░      ▒████
                          ██▒         ░▒▓███▒    ▒█▒█▒
                            ░▓█            ███   ▓░▒██
                              ▓█       ▒▒▒▒▒▓██▓░▒░▓▓█
                            █░ █   ▒▒░       ███▓▓█ ▒█▒▒▒
                            ████░   ▒▓█▓      ██▒▒▒ ▓███▒
                         ░▒█▓▓██       ▓█▒    ▓█▒▓██▓ ░█░
                   ▓░▒▓████▒ ██         ▒█    █▓░▒█▒░▒█▒
                  ███▓░██▓  ▓█           █   █▓ ▒▓█▓▓█▒
                ░██▓  ░█░            █  █▒ ▒█████▓▒ ██▓░▒
               ███░ ░ █░          ▓ ░█ █████▒░░    ░█░▓  ▓░
              ██▓█ ▒▒▓▒          ▓███████▓░       ▒█▒ ▒▓ ▓██▓
           ▒██▓ ▓█ █▓█       ░▒█████▓▓▒░         ██▒▒  █ ▒  ▓█▒
           ▓█▓  ▓█ ██▓ ░▓▓▓▓▓▓▓▒              ▒██▓           ░█▒
           ▓█    █ ▓███▓▒░              ░▓▓▓███▓          ░▒░ ▓█
           ██▓    ██▒    ░▒▓▓███▓▓▓▓▓██████▓▒            ▓███  █
          ▓███▒ ███   ░▓▓▒░░   ░▓████▓░                  ░▒▓▒  █▓
          █▓▒▒▓▓██  ░▒▒░░░▒▒▒▒▓██▓░                            █▓
          ██ ▓░▒█   ▓▓▓▓▒░░  ▒█▓       ▒▓▓██▓    ▓▒          ▒▒▓
          ▓█▓ ▓▒█  █▓░  ░▒▓▓██▒            ░▓█▒   ▒▒▒░▒▒▓█████▒
           ██░ ▓█▒█▒  ▒▓▓▒  ▓█                █░      ░░░░   ░█▒
           ▓█   ▒█▓   ░     █░                ▒█              █▓
            █▓   ██         █░                 ▓▓        ▒█▓▓▓▒█░
             █▓ ░▓██░       ▓▒                  ▓█▓▒░░░▒▓█░    ▒█
              ██   ▓█▓░      ▒                    ░▒█▒██▒      ▓▓
               ▓█▒   ▒█▓▒░                         ▒▒ █▒█▓▒▒░░▒██
                ░██▒    ▒▓▓▒                     ▓██▓▒█▒ ░▓▓▓▓▒█▓
                  ░▓██▒                          ▓░  ▒█▓█  ░░▒▒▒
                      ▒▓▓▓▓▓▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒░░▓▓  ▓░▒█░

    ______ _ _       _       _____  ____  _         _____ _ _            _  BETA   
   |  ____| (_)     | |     / ____|/ __ \| |       / ____| (_)          | |  
   | |__  | |_ _ __ | | __ | (___ | |  | | |      | |    | |_  ___ _ __ | |_
   |  __| | | | '_ \| |/ /  \___ \| |  | | |      | |    | | |/ _ \ '_ \| __|
   | |    | | | | | |   <   ____) | |__| | |____  | |____| | |  __/ | | | |_
   |_|    |_|_|_| |_|_|\_\ |_____/ \___\_\______|  \_____|_|_|\___|_| |_|\__|

        Welcome! Enter 'HELP;' to list all available commands. 'QUIT;' to exit.


Flink SQL>
```
PS: to flush queue:
docker exec -ti broker /usr/bin/kafka-topics --bootstrap-server localhost:9092 --delete --topic fhv-trips
docker exec -ti broker /usr/bin/kafka-topics --bootstrap-server localhost:9092 --delete --topic green-trips
