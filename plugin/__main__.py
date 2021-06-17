import click
import time
from plugin.block import SyncMongodbProcess


@click.command()
@click.option(
    '--web3-url',
    required=True,
    default="",
    type=click.STRING,
    help="web3-url which is required before processing requests",
)
@click.option(
    '--start-block',
    required=True,
    default=0,
    type=click.INT,
    help="start_block which is required before processing requests",
)
@click.option(
    '--mongo-host',
    required=True,
    default="",
    type=click.STRING,
    help="mongo-host which is required before processing requests",
)
@click.option(
    '--mongo-username',
    required=True,
    default="",
    type=click.STRING,
    help="mongo-username which is required before processing requests",
)
@click.option(
    '--mongo-passwd',
    required=True,
    default="",
    type=click.STRING,
    help="mongo-passwd which is required before processing requests",
)
@click.option(
    '--mongo-database',
    required=True,
    default="",
    type=click.STRING,
    help="mongo-database which is required before processing requests",
)
@click.option(
    '--mongo-database-v2',
    required=True,
    default="",
    type=click.STRING,
    help="mongo-database-v2 which is required before processing requests",
)
def main(
        web3_url: str,
        start_block: int,
        mongo_host: str,
        mongo_username: str,
        mongo_passwd: str,
        mongo_database: str,
        mongo_database_v2: str,
):
    print(web3_url, start_block, mongo_host, mongo_username, mongo_passwd, mongo_database, mongo_database_v2, )
    tasks = [
        SyncMongodbProcess(web3_url, start_block,
                           mongo_host, mongo_username, mongo_passwd,
                           mongo_database, mongo_database_v2, ),
        # SyncHistoryProcess(web3_url, mongo_database, mongo_host, mongo_username, mongo_passwd),
    ]

    for t in tasks:
        t.start()

    while True:
        time.sleep(3)
        Q = False
        for t in tasks:
            if not t.is_alive():
                Q = True
        if Q:
            for t in tasks:
                t.terminate()
                print('stop process {}'.format(t))
                t.join()
            break
    print("exiting ... ")


if __name__ == '__main__':
    main(auto_envvar_prefix="EP")
