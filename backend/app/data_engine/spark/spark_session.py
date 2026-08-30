"""
Central SparkSession factory.

One Spark session is created per pipeline run (bronze -> silver -> gold) and
closed at the end. Configuration is driven entirely by environment variables
so the same code runs unchanged whether Spark is running in local[*] mode
inside the backend container (Nexus V1's default) or pointed at a real
cluster master later (see docs/TECHNICAL_LEARNING_GUIDE.md, "Scalability").
"""
import os

from pyspark.sql import SparkSession


def get_spark_session(app_name: str = "nexus-pipeline") -> SparkSession:
    spark_master = os.getenv("SPARK_MASTER", "local[*]")
    mysql_jar_path = os.getenv("MYSQL_JDBC_JAR", "/opt/spark-jars/mysql-connector-j.jar")

    builder = (
        SparkSession.builder
        .appName(app_name)
        .master(spark_master)
        .config("spark.sql.session.timeZone", "UTC")
        .config("spark.sql.shuffle.partitions", os.getenv("SPARK_SHUFFLE_PARTITIONS", "8"))
        .config("spark.driver.memory", os.getenv("SPARK_DRIVER_MEMORY", "2g"))
        .config("spark.sql.legacy.timeParserPolicy", "CORRECTED")
    )

    if os.path.exists(mysql_jar_path):
        builder = builder.config("spark.jars", mysql_jar_path)

    spark = builder.getOrCreate()
    spark.sparkContext.setLogLevel(os.getenv("SPARK_LOG_LEVEL", "WARN"))
    return spark


def mysql_jdbc_options() -> dict:
    """Common JDBC connection options for reading/writing Gold tables to MySQL."""
    host = os.getenv("MYSQL_HOST", "mysql")
    port = os.getenv("MYSQL_PORT", "3306")
    database = os.getenv("MYSQL_DATABASE", "nexus")
    user = os.getenv("MYSQL_USER", "nexus")
    password = os.getenv("MYSQL_PASSWORD", "")
    return {
        "url": f"jdbc:mysql://{host}:{port}/{database}?useSSL=false&allowPublicKeyRetrieval=true",
        "driver": "com.mysql.cj.jdbc.Driver",
        "user": user,
        "password": password,
    }
