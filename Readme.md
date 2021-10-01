# Annotated VCF parser 


```python
reader = VcfReader("myvcf.vcf", "vep")

for variant in reader: 
  print(variant["annotations"][0]["impact"]
 
```
