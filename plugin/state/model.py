from mongoengine import *
from datetime import datetime


class EthUserInfo(Document):
    address = StringField(required=True, unique=True)
    tokens = ListField()
    state = IntField(default=0)
    creation_date = DateTimeField(default=datetime.utcnow)
    modified_date = DateTimeField(default=datetime.utcnow)

    meta = {
        'db_alias': 'wallet-service',
        'indexes': [
            'address',
            'state'
        ],
    }

    def save(self, *args, **kwargs):
        if not self.creation_date:
            self.creation_date = datetime.utcnow()
        self.modified_date = datetime.utcnow()
        return super(EthUserInfo, self).save(*args, **kwargs)


class EthSyncStatusV2(Document):
    network_id = IntField(required=True)
    confirmed_head_number = LongField()
    confirmed_head_hash = StringField(max_length=66)
    unconfirmed_head_number = LongField()
    unconfirmed_head_hash = StringField(max_length=66)
    meta = {
        'db_alias': 'wallet-service-v2',
        'indexes': [
            'network_id',
        ],
    }


class ERCTokenV2(EmbeddedDocument):
    _address = StringField(required=True)
    _from = StringField(required=True)
    _to = StringField(required=True)
    _value = StringField(required=True)
    _logIndex = IntField(required=True)


class EthTransactionV2(Document):
    hash = StringField(required=True)
    blockHash = StringField()
    blockNumber = LongField(required=True)
    contractAddress = StringField(required=False)
    from_ = StringField(required=True)
    gas = StringField(required=True)
    gasUsed = StringField(required=True)
    gasPrice = StringField(required=True)
    input = StringField(required=True)
    logs = EmbeddedDocumentListField(ERCTokenV2)
    nonce = StringField(required=True)
    status = IntField()
    to_ = StringField()
    transactionIndex = IntField(required=True)
    value_ = StringField(required=True)
    timestamp = LongField(required=True)
    confirmations = LongField()
    creation_date = DateTimeField(default=datetime.utcnow)
    modified_date = DateTimeField(default=datetime.utcnow)

    meta = {
        'db_alias': 'wallet-service-v2',
        'indexes': [
            'hash',
            'blockNumber',
            'from_',
            'to_',
            'confirmations',
            'logs._address',
            'logs._from',
            'logs._to',
            'logs._logIndex',
        ]
    }

    def save(self, *args, **kwargs):
        if not self.creation_date:
            self.creation_date = datetime.utcnow()
        self.modified_date = datetime.utcnow()
        return super(EthTransactionV2, self).save(*args, **kwargs)

