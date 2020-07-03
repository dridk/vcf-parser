from mongoengine import *

connect("vcf")
from vcfreader import VcfReader
import sys


class Variant(DynamicDocument):
    pass
    # chrom = StringField(required=True)
    # pos = IntField(required=True)
    # ref = StringField(required=True)
    # alt = StringField(required=True)


reader = VcfReader(open("test.snpeff.vcf"), "snpeff")


for data in reader.get_variants():

    variant = Variant(**data)

    variant.save()
