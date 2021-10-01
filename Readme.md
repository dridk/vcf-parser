# Annotated VCF parser 


```python
from vcfReader import VcfReader
reader = VcfReader("myvcf.vcf", "vep")

for variant in reader: 
  print(variant["annotations"][0]["impact"]
 
```
