## Annotated VCF parser 

It supports vep and snpeff annotations

```python
from vcfReader import VcfReader
reader = VcfReader("myvcf.vcf", "vep")

for variant in reader: 
  print(variant["annotations"][0]["impact"]
 
```
