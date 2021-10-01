## Annotated VCF parser 

It supports vep and snpeff annotations

```python
from vcfReader import VcfReader
reader = VcfReader("myvcf.vcf", "vep")

for variant in reader.get_variants(): 
  print(variant["annotations"][0]["impact"]
 
```
