import multiprocessing
import sys
import time
from concurrent.futures import ThreadPoolExecutor

from mongoengine import errors
from requests.exceptions import ConnectionError, ReadTimeout
from web3 import Web3

from plugin.log import run_log as log
from plugin.state import ManagerState
from plugin.utils import ERC20_ABI


class SyncMongodbProcess(multiprocessing.Process):
    def __init__(self, web3_url, start_block,
                 mongo_host, mongo_username, mongo_passwd,
                 mongo_database, mongo_database_v2, ):
        multiprocessing.Process.__init__(self)
        self.mongo_parma = {"mongo_host": mongo_host, "mongo_username": mongo_username, "mongo_passwd": mongo_passwd,
                            "mongo_database": mongo_database, "mongo_database_v2": mongo_database_v2}
        self.poll_interval = 2
        self.sync_start_block = start_block
        self.confirmation_blocks = 2
        self.web3 = Web3(Web3.HTTPProvider(web3_url, request_kwargs={'timeout': 60}))
        self.executor = ThreadPoolExecutor(max_workers=8)

    def run(self):
        self.state = ManagerState(
            self.mongo_parma['mongo_host'],
            self.mongo_parma['mongo_username'], self.mongo_parma['mongo_passwd'],
            self.mongo_parma['mongo_database'], self.mongo_parma['mongo_database_v2'],
            2020,
        )
        log.info('starting blockchain polling (interval {})'.format(self.poll_interval))
        while True:
            try:
                self._update()
                self._re_scan_unconfirmed_txn()
            except (ConnectionError, ReadTimeout) as e:
                endpoint = self.web3.manager.provider.endpoint_uri
                log.warning(
                    'Ethereum node (%s) refused connection. Retrying in %d seconds. ErrorInfo %s' %
                    (endpoint, self.poll_interval, e)
                )

            time.sleep(self.poll_interval)

    def _update(self):
        new_unconfirmed_head_number = self.web3.eth.blockNumber

        # Handle testing with private chains. The block number can be
        # smaller than confirmation_blocks
        new_confirmed_head_number = max(0, new_unconfirmed_head_number - self.confirmation_blocks)

        if self.state.confirmed_head_number is None:
            self.state.update_sync_state(confirmed_head_number=self.sync_start_block)
        if self.state.unconfirmed_head_number is None:
            self.state.update_sync_state(unconfirmed_head_number=self.sync_start_block)

        # filter tx
        users = self.state.users

        # 左闭右开
        self._filter_eth(self.state.confirmed_head_number + 1, new_confirmed_head_number + 1, users)
        # 左闭右开
        self._filter_erc20(self.state.confirmed_head_number + 1, new_confirmed_head_number + 1, users)

        try:
            new_unconfirmed_head_hash = self.web3.eth.getBlock(new_unconfirmed_head_number).hash.hex()
            new_confirmed_head_hash = self.web3.eth.getBlock(new_confirmed_head_number).hash.hex()
        except AttributeError:
            log.critical("RPC endpoint didn't return proper info for an existing block "
                         "(%d,%d)" % (new_unconfirmed_head_number, new_confirmed_head_number))
            log.critical("It is possible that the blockchain isn't fully synced. "
                         "This often happens when Parity is run with --fast or --warp sync.")
            log.critical("Can't continue - check status of the ethereum node.")
            sys.exit(1)

        self.state.update_sync_state(unconfirmed_head_number=new_unconfirmed_head_number,
                                     unconfirmed_head_hash=new_unconfirmed_head_hash,
                                     confirmed_head_number=new_confirmed_head_number,
                                     confirmed_head_hash=new_confirmed_head_hash)

        log.debug(
            "sync block info\n"
            "new_unconfirmed_head_number: {}, new_unconfirmed_head_hash: {}\n"
            "new_confirmed_head_number:   {}, new_confirmed_head_hash:   {}\n".format(
                new_unconfirmed_head_number, new_unconfirmed_head_hash,
                new_confirmed_head_number, new_confirmed_head_hash))

    def _filter_eth(self, from_block: int, to_block: int, users):
        for i in range(from_block, to_block, 1):
            log.info("syncing eth start_block ：%s, i : %s, last_block : %s" % (from_block, i, to_block))

            block = self.web3.eth.getBlock(i)
            transactions = block.transactions

            for tx in transactions:
                flag = False
                tx_data = self.web3.eth.getTransaction(tx)

                # filter eth
                if tx_data.get('from') in users or tx_data.get('to') in users:
                    flag = True

                if not flag:
                    continue

                tx_receipt = self.web3.eth.getTransactionReceipt(tx)
                tx_info = dict([
                    ('hash', Web3.toHex(tx_receipt.get('transactionHash'))),
                    ('blockHash', Web3.toHex(tx_receipt.get('blockHash'))),
                    ('blockNumber', tx_receipt.get('blockNumber')),
                    ('contractAddress', tx_receipt.get('contractAddress')),
                    ('from_', tx_receipt.get('from')),
                    ('gas', str(tx_receipt.get('cumulativeGasUsed'))),
                    ('gasUsed', str(tx_receipt.get('gasUsed'))),
                    ('gasPrice', str(tx_data.get('gasPrice'))),
                    ('input', tx_data.get('input')),
                    ('logs', []),
                    ('status', tx_receipt.get('status')),
                    ('nonce', str(tx_data.get('nonce'))),
                    ('to_', tx_receipt.get('to')),
                    ('transactionIndex', tx_receipt.get('transactionIndex')),
                    ('value_', str(tx_data.get('value'))),
                    ('timestamp', block.get('timestamp')),
                    ('confirmations', to_block - tx_receipt.get('blockNumber')),
                ])

                # filter failed erc20
                if tx_info.get('from_') in users and tx_info.get('status') == 0:
                    input = tx_data.get("input")
                    if input:
                        contract = self.web3.eth.contract(
                            address=Web3.toChecksumAddress("0x0000000000000000000000000000000000000000"),
                            abi=ERC20_ABI,
                        )

                        try:
                            input_data = contract.decode_function_input(input)[1]
                            if input_data:
                                input_decode = dict([
                                    ('_address', tx_receipt.get('to')),
                                    ('_from', tx_receipt.get('from')),
                                    ('_to', input_data.get('recipient')),
                                    ('_value', str(input_data.get('amount'))),
                                    ('_logIndex', 0),
                                ])
                                if input_decode.get('_from') is not None and input_decode.get(
                                        '_to') is not None and input_decode.get('_value') is not None:
                                    tx_info.update({'logs': [input_decode]})
                                    flag = True
                        except Exception as err:
                            log.debug("decode_function_input failed err: {}".format(err))

                if flag:
                    try:
                        self.state.upsert_txinfo(**tx_info)
                    except Exception as e:
                        log.error('upsert_txinfo %s tx_info %s)' % (e, tx_info))
                        continue
                    log.info('insert, tx_info %s)' % tx_info)

    # filter success erc20
    def _filter_erc20(self, from_block: int, to_block: int, users: list, ):
        if from_block > to_block:
            return

        for i in range(from_block, to_block, 1):
            log.info("syncing erc start_block ：%s, i : %s, last_block : %s" % (from_block, i, to_block))
            transfer_tasks = []
            tasks_results = []

            # only filter special token
            # for token in tokens:
            #     event_signature_transfer = Web3.sha3(text='Transfer(address,address,uint256)').hex()
            #     event_filter = dict([
            #         ("address", token.address),
            #         ("fromBlock", from_block),
            #         ("toBlock", to_block),
            #         ("symbol", token.symbol),
            #         ("topics", [event_signature_transfer])
            #     ])
            #     transfer_tasks.append(event_filter)

            # now filter all erc20
            event_signature_transfer = Web3.sha3(text='Transfer(address,address,uint256)').hex()
            event_filter = dict([
                ("fromBlock", i),
                ("toBlock", i),
                ("topics", [event_signature_transfer])
            ])
            transfer_tasks.append(event_filter)

            for param, result in zip(transfer_tasks, self.executor.map(self.web3.eth.getLogs, transfer_tasks)):
                if result:
                    tasks_results.append((param, result))

            for tx in tasks_results:
                flag = False
                filers, tlogs = tx[0], tx[1]

                for tlog in tlogs:
                    contract = self.web3.eth.contract(
                        address=Web3.toChecksumAddress("0x0000000000000000000000000000000000000000"),
                        abi=ERC20_ABI,
                    )
                    try:
                        logdata = contract.events.Transfer().processLog(tlog)
                    except Exception as err:
                        continue

                    if logdata.get('args').get('from') is None or logdata.get('args').get('to') is None or logdata.get(
                            'args').get('value') is None:
                        continue

                    input_decode = dict([
                        ('_address', tlog.get('address')),
                        ('_from', logdata.get('args').get('from')),
                        ('_to', logdata.get('args').get('to')),
                        ('_value', str(logdata.get('args').get('value'))),
                        ('_logIndex', logdata.get('logIndex')),
                    ])

                    if input_decode["_from"] not in users and input_decode["_to"] not in users:
                        continue

                    tx_hash = tlog.get('transactionHash')
                    tx_data = self.web3.eth.getTransaction(tx_hash)
                    tx_receipt = self.web3.eth.getTransactionReceipt(tx_hash)
                    block = self.web3.eth.getBlock(tlog['blockNumber'])

                    tx_info = dict([
                        ('hash', Web3.toHex(tx_receipt.get('transactionHash'))),
                        ('blockHash', Web3.toHex(tx_receipt.get('blockHash'))),
                        ('blockNumber', tx_receipt.get('blockNumber')),
                        ('contractAddress', tx_receipt.get('contractAddress')),
                        ('from_', tx_receipt.get('from')),
                        ('gas', str(tx_receipt.get('cumulativeGasUsed'))),
                        ('gasUsed', str(tx_receipt.get('gasUsed'))),
                        ('gasPrice', str(tx_data.get('gasPrice'))),
                        ('input', tx_data.get('input')),
                        ('logs', [input_decode]),
                        ('status', tx_receipt.get('status')),
                        ('nonce', str(tx_data.get('nonce'))),
                        ('to_', tx_receipt.get('to')),
                        ('transactionIndex', tx_receipt.get('transactionIndex')),
                        ('value_', str(tx_data.get('value'))),
                        ('timestamp', block.get('timestamp')),
                        ('confirmations', to_block - tx_receipt.get('blockNumber')),
                    ])

                    if input_decode["_from"] in users or input_decode["_to"] in users:
                        flag = True

                    if flag:
                        try:
                            self.state.upsert_txinfo(**tx_info)
                        except Exception as e:
                            log.error('upsert_txinfo %s tx_info %s)' % (e, tx_info))
                            continue
                        log.info('upsert, tx_info %s)' % tx_info)

    def _re_scan_unconfirmed_txn(self):
        txs = self.state.unconfirmed_txinfo
        block_number = self.web3.eth.blockNumber
        for tx in txs:
            tx_receipt = self.web3.eth.getTransactionReceipt(tx.hash)
            if not tx_receipt:
                log.error("get txn receipt failed, hash: {}".format(tx.hash))
                tx.delete()
            else:
                tx_data = self.web3.eth.getTransaction(tx.hash)
                block = self.web3.eth.getBlock(tx_receipt.get('blockNumber'))
                if tx_receipt.get('blockNumber') != tx.blockNumber or \
                        Web3.toHex(tx_receipt.get('blockHash')) != tx.blockHash or \
                        str(tx_receipt.get('gasUsed')) != tx.gasUsed or \
                        str(tx_data.get('gasPrice')) != tx.gasPrice or \
                        tx_receipt.get('status') != tx.status or \
                        tx_receipt.get('transactionIndex') != tx.transactionIndex or \
                        block.get('timestamp') != tx.timestamp:
                    tx.blockHash = Web3.toHex(tx_receipt.get('blockHash'))
                    tx.blockNumber = tx_receipt.get('blockNumber')
                    tx.contractAddress = tx_receipt.get('contractAddress')
                    tx.from_ = tx_receipt.get('from')
                    tx.gas = str(tx_receipt.get('cumulativeGasUsed'))
                    tx.gasUsed = str(tx_receipt.get('gasUsed'))
                    tx.gasPrice = str(tx_data.get('gasPrice'))
                    tx.input = tx_data.get('input')
                    tx.status = tx_receipt.get('status')
                    tx.nonce = str(tx_data.get('nonce'))
                    tx.to_ = tx_receipt.get('to')
                    tx.transactionIndex = tx_receipt.get('transactionIndex')
                    tx.value_ = str(tx_data.get('value'))
                    tx.timestamp = block.get('timestamp')
                    tx.confirmations = block_number - tx_receipt.get('blockNumber')

                    log.info("block reorganization detected, new tx_info: {}".format(tx))
                else:
                    tx.confirmations = block_number - tx.blockNumber

                tx.save()