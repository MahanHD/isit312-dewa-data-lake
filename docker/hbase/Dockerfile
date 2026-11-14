FROM docker.io/library/eclipse-temurin:17-jre
ARG V=2.6.7
ARG SHA512=2e0835a3ed8e5a9114f5d878deafb2f7a6b1c8386ba422d1a307fcc5551d452dc7da468729a43acf75dcfe0b20424cb48f72ed424dfd15f81b1b3624454ed82d
RUN curl -fsSL -o /tmp/hbase.tgz https://archive.apache.org/dist/hbase/$V/hbase-$V-hadoop3-bin.tar.gz \
 && echo "$SHA512  /tmp/hbase.tgz" | sha512sum -c - \
 && mkdir /opt/hbase && tar -xzf /tmp/hbase.tgz -C /opt/hbase --strip-components=1 && rm /tmp/hbase.tgz
ENV HBASE_HOME=/opt/hbase PATH=/opt/hbase/bin:$PATH HBASE_HEAPSIZE=1G HBASE_MANAGES_ZK=true
COPY hbase-site.xml /opt/hbase/conf/hbase-site.xml
# standalone mode: master, region server and ZooKeeper in one JVM; table data lives in HDFS
CMD ["hbase", "master", "start"]
