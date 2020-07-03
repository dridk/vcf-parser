from vcfreader import VcfReader

import sys


reader = VcfReader(open("test.snpeff.vcf"), "snpeff")

print(reader.get_samples())

print(reader.get_fields())

for variant in reader.get_variants():
    print(variant)
