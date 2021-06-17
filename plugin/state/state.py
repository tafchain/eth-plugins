from mongoengine import *
from datetime import datetime
from .model import EthSyncStatusV2, EthTransactionV2, EthUserInfo


class ManagerState(object):
    def __init__(self, url, username, password, database, database_v2, network_id=None):
        connect(database, host=url, username=username, password=password, authentication_source='admin',
                alias='wallet-service')
        connect(database_v2, host=url, username=username, password=password, authentication_source='admin',
                alias='wallet-service-v2')
        if network_id:
            self.network_id = network_id
            block = EthSyncStatusV2.objects(network_id=self.network_id).first()
            if not block:
                bk = EthSyncStatusV2(network_id=self.network_id)
                bk.save()

    @property
    def _sync_state(self):
        block = EthSyncStatusV2.objects(network_id=self.network_id).first()
        return block

    @property
    def confirmed_head_number(self):
        """The number of the highest processed block considered to be final."""
        return self._sync_state.confirmed_head_number

    @confirmed_head_number.setter
    def confirmed_head_number(self, value):
        self.update_sync_state(confirmed_head_number=value)

    @property
    def confirmed_head_hash(self):
        """The hash of the highest processed block considered to be final."""
        return self._sync_state.confirmed_head_hash

    @confirmed_head_hash.setter
    def confirmed_head_hash(self, value):
        self.update_sync_state(confirmed_head_hash=value)

    @property
    def unconfirmed_head_number(self):
        """The number of the highest processed block considered to be not yet final."""
        return self._sync_state.unconfirmed_head_number

    @unconfirmed_head_number.setter
    def unconfirmed_head_number(self, value: int):
        self.update_sync_state(unconfirmed_head_number=value)

    @property
    def unconfirmed_head_hash(self):
        """The hash of the highest processed block considered to be not yet final."""
        return self._sync_state.unconfirmed_head_hash

    @unconfirmed_head_hash.setter
    def unconfirmed_head_hash(self, value: str):
        self.update_sync_state(unconfirmed_head_hash=value)

    def update_sync_state(
            self,
            confirmed_head_number=None,
            confirmed_head_hash=None,
            unconfirmed_head_number=None,
            unconfirmed_head_hash=None
    ):
        """Update block numbers and hashes of confirmed and unconfirmed head."""
        block = EthSyncStatusV2.objects(network_id=self.network_id)
        if confirmed_head_number is not None:
            block.update_one(set__confirmed_head_number=confirmed_head_number)
        if confirmed_head_hash is not None:
            block.update_one(set__confirmed_head_hash=confirmed_head_hash)
        if unconfirmed_head_number is not None:
            block.update_one(set__unconfirmed_head_number=unconfirmed_head_number)
        if unconfirmed_head_hash is not None:
            block.update_one(set__unconfirmed_head_hash=unconfirmed_head_hash)

    @property
    def users(self):
        users = set([u.address for u in EthUserInfo.objects.only('address').all()])
        return users

    @property
    def new_users(self):
        users = EthUserInfo.objects(state__ne=1).all()
        return users

    def update_user_state(self, address):
        EthUserInfo.objects(address=address).update_one(set__state=1)

    # @property
    # def tokens(self):
    #     tokens = EthToken.objects.all()
    #     return tokens
    #
    # def set_token(self, **token):
    #     token = EthToken(**token)
    #     token.save()

    def set_txinfo(self, **tx_info):
        tx = EthTransactionV2(**tx_info)
        tx.save()

    def upsert_txinfo(self, **tx_info):
        txn = EthTransactionV2.objects(hash=tx_info.get('hash')).upsert_one(
            set__hash=tx_info.get('hash'),
            set__blockHash=tx_info.get('blockHash'),
            set__blockNumber=tx_info.get('blockNumber'),
            set__contractAddress=tx_info.get('contractAddress'),
            set__from_=tx_info.get('from_'),
            set__gas=tx_info.get('gas'),
            set__gasUsed=tx_info.get('gasUsed'),
            set__gasPrice=tx_info.get('gasPrice'),
            set__input=tx_info.get('input'),
            # set__logs=tx_info.get('logs'),
            set__nonce=tx_info.get('nonce'),
            set__status=tx_info.get('status'),
            set__to_=tx_info.get('to_'),
            set__transactionIndex=tx_info.get('transactionIndex'),
            set__value_=tx_info.get('value_'),
            set__timestamp=tx_info.get('timestamp'),
            set__confirmations=tx_info.get('confirmations'),
            set__creation_date=datetime.utcnow(),
            set__modified_date=datetime.utcnow(),
        )
        logs = tx_info.get('logs')
        if logs:
            mlog = logs[0]
            if mlog:
                existing = txn.logs.filter(_logIndex=mlog.get('_logIndex'))
                if existing.count() == 0:
                    txn.logs.create(**mlog)
                else:
                    existing.update(**mlog)
                txn.save()

    @property
    def unconfirmed_txinfo(self):
        tx = EthTransactionV2.objects(Q(confirmations__exists=False) | Q(confirmations__lte=6)).all()
        return tx
