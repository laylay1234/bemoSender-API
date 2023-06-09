#!/usr/bin/env bash
set -x

##
# Delete migration first
##

# dev
tbl=$(mysql --host=$RDSHOST --port=3306 --user=${USER} --password=$PASS --ssl-ca=rds-ca-2019-root.pem --ssl dev_v1_connect -e'show tables;'|grep -v Tables_in_dev_v1_connect)
for i in $tbl;do mysql --host=$RDSHOST --port=3306 --user=${USER} --password=$PASS --ssl-ca=rds-ca-2019-root.pem --ssl dev_v1_connect -e"SET FOREIGN_KEY_CHECKS = 0;drop table $i;SET FOREIGN_KEY_CHECKS = 1;";done

# test
tbl=$(mysql --host=$RDSHOST --port=3306 --user=${USER} --password=$PASS --ssl-ca=rds-ca-2019-root.pem --ssl test_v1_connect -e'show tables;'|grep -v Tables_in)
for i in $tbl;do mysql --host=$RDSHOST --port=3306 --user=${USER} --password=$PASS --ssl-ca=rds-ca-2019-root.pem --ssl test_v1_connect -e"SET FOREIGN_KEY_CHECKS = 0;drop table $i;SET FOREIGN_KEY_CHECKS = 1;";done
tbl=$(mysql --host=$RDSHOST --port=3306 --user=${USER} --password=$PASS --ssl-ca=rds-ca-2019-root.pem --ssl test_v1_connect_1 -e'show tables;'|grep -v Tables_in)
for i in $tbl;do mysql --host=$RDSHOST --port=3306 --user=${USER} --password=$PASS --ssl-ca=rds-ca-2019-root.pem --ssl test_v1_connect_1 -e"SET FOREIGN_KEY_CHECKS = 0;drop table $i;SET FOREIGN_KEY_CHECKS = 1;";done
tbl=$(mysql --host=$RDSHOST --port=3306 --user=${USER} --password=$PASS --ssl-ca=rds-ca-2019-root.pem --ssl test_v1_connect_2 -e'show tables;'|grep -v Tables_in)
for i in $tbl;do mysql --host=$RDSHOST --port=3306 --user=${USER} --password=$PASS --ssl-ca=rds-ca-2019-root.pem --ssl test_v1_connect_2 -e"SET FOREIGN_KEY_CHECKS = 0;drop table $i;SET FOREIGN_KEY_CHECKS = 1;";done
tbl=$(mysql --host=$RDSHOST --port=3306 --user=${USER} --password=$PASS --ssl-ca=rds-ca-2019-root.pem --ssl test_v1_connect_3 -e'show tables;'|grep -v Tables_in)
for i in $tbl;do mysql --host=$RDSHOST --port=3306 --user=${USER} --password=$PASS --ssl-ca=rds-ca-2019-root.pem --ssl test_v1_connect_3 -e"SET FOREIGN_KEY_CHECKS = 0;drop table $i;SET FOREIGN_KEY_CHECKS = 1;";done
tbl=$(mysql --host=$RDSHOST --port=3306 --user=${USER} --password=$PASS --ssl-ca=rds-ca-2019-root.pem --ssl test_v1_connect_4 -e'show tables;'|grep -v Tables_in)
for i in $tbl;do mysql --host=$RDSHOST --port=3306 --user=${USER} --password=$PASS --ssl-ca=rds-ca-2019-root.pem --ssl test_v1_connect_4 -e"SET FOREIGN_KEY_CHECKS = 0;drop table $i;SET FOREIGN_KEY_CHECKS = 1;";done

set -e

ENV='Dev-V3' python3 manage.py migrate
ENV="Dev-V3" python3 manage.py loaddata bemoSenderr/fixtures/users.json


DB_NAME='test_v1_connect' ENV='Test-V1' python3 manage.py migrate
DB_NAME='test_v1_connect_1' ENV='Test-V1' python3 manage.py migrate
DB_NAME='test_v1_connect_2' ENV='Test-V1' python3 manage.py migrate
DB_NAME='test_v1_connect_3' ENV='Test-V1' python3 manage.py migrate
DB_NAME='test_v1_connect_4' ENV='Test-V1' python3 manage.py migrate

bin/clean.sh