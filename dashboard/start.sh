#!/usr/bin/env bash
set -euo pipefail
cd /opt/zeppelin
jar=/opt/zeppelin/hive-jdbc-4.0.1-standalone.jar
if [[ ! -s $jar ]]; then
  echo "Downloading the Hive JDBC driver (about 45 MB, first start only)"
  wget -q -O "$jar.part" https://repo1.maven.org/maven2/org/apache/hive/hive-jdbc/4.0.1/hive-jdbc-4.0.1-standalone.jar
  mv "$jar.part" "$jar"
fi
export JAVA_HOME="$(dirname "$(dirname "$(readlink -f "$(command -v java)")")")"
python /workspace/dashboard/setup.py notebook
python /workspace/dashboard/setup.py interpreter "$jar" &
exec bin/zeppelin.sh
